#!/usr/bin/env python3
"""MCP server for reading YouTube: channel uploads, search, and transcripts.

Built for injury-analysis channels (a sports-medicine doctor breaking down the
replay of an injury says more about a return timeline than the team's first
injury report does), but any channel works.

    channel_videos    a channel's uploads, or a search inside one channel
    search_youtube    YouTube-wide search, optionally limited to a channel
    player_videos     search every watched channel for one player
    video_transcript  the transcript of one video, with title and upload date
    watched_channels / watch_channel
                      the channels player_videos searches (channels.json)

No API key: listings and metadata come from yt-dlp, transcripts from
youtube-transcript-api. yt-dlp's own subtitle download gets HTTP 429 from
YouTube where the transcript API does not, which is why there are two
libraries. Transcripts and metadata are cached under cache/ (gitignored);
transcript text is the creator's work, so read it here and summarise it, but
do not commit it — this repo is public.

Run standalone:  python mcp_server.py
Register:        see .mcp.json at the repo root (engine/mcp_launch.sh youtube)
"""

import json
import pathlib
import re
from datetime import datetime, timezone

from mcp.server.mcpserver import MCPServer

HERE = pathlib.Path(__file__).resolve().parent
CHANNELS = HERE / "channels.json"
CACHE = HERE / "cache"
TRANSCRIPTS = CACHE / "transcripts"
META = CACHE / "meta.json"

mcp = MCPServer("ff-youtube", version="1.0.0")


# ------------------------------------------------------------------ helpers

def _ydl(**opts):
    import yt_dlp
    base = {"quiet": True, "no_warnings": True, "skip_download": True,
            "extract_flat": True}
    base.update(opts)
    return yt_dlp.YoutubeDL(base)


def _video_id(url_or_id):
    s = url_or_id.strip()
    m = re.search(r"(?:v=|youtu\.be/|/shorts/|/live/|/embed/)([\w-]{11})", s)
    if m:
        return m.group(1)
    if re.fullmatch(r"[\w-]{11}", s):
        return s
    raise ValueError(f"not a YouTube video URL or id: {url_or_id!r}")


def _read_channels():
    if not CHANNELS.exists():
        return []
    return json.loads(CHANNELS.read_text(encoding="utf-8"))


def _channel_url(channel):
    """Base URL for '@handle', a channel URL, a UC... id, or a watched
    channel's name as channels.json spells it."""
    c = channel.strip().rstrip("/")
    for row in _read_channels():
        if c.lower() in (row["name"].lower(), row["handle"].lower(),
                         row["handle"].lstrip("@").lower()):
            c = row["handle"]
            break
    if c.startswith("http"):
        return re.sub(r"/(videos|shorts|streams|featured|search.*)$", "", c)
    if c.startswith("UC") and len(c) == 24:
        return f"https://www.youtube.com/channel/{c}"
    return f"https://www.youtube.com/@{c.lstrip('@')}"


def _videos_only(entries):
    """Drop playlists and channels, which a channel search mixes in."""
    return [e for e in entries or []
            if e.get("id") and len(e["id"]) == 11 and e.get("duration")]


def _read_meta():
    if META.exists():
        return json.loads(META.read_text(encoding="utf-8"))
    return {}


def _write_meta(meta):
    CACHE.mkdir(exist_ok=True)
    META.write_text(json.dumps(meta, indent=1), encoding="utf-8")


def _metadata(vid, meta=None):
    """Title, channel, upload date and description of one video, cached.

    Flat listings carry no dates, so anything that needs one comes here: one
    request per video, and never again for the same video."""
    own = meta is None
    meta = _read_meta() if own else meta
    if vid not in meta:
        with _ydl(extract_flat=False, ignore_no_formats_error=True) as y:
            i = y.extract_info(f"https://www.youtube.com/watch?v={vid}",
                               download=False, process=False)
        meta[vid] = {
            "title": i.get("title"), "channel": i.get("channel"),
            "handle": i.get("uploader_id"), "upload_date": i.get("upload_date"),
            "duration": i.get("duration"), "view_count": i.get("view_count"),
            "description": (i.get("description") or "")[:1500]}
        if own:
            _write_meta(meta)
    return meta[vid]


def _date(yyyymmdd):
    if not yyyymmdd:
        return "?"
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"


def _mmss(seconds):
    if not seconds:
        return "?"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    return f"{h}:{rem // 60:02d}:{rem % 60:02d}" if h else f"{rem // 60}:{rem % 60:02d}"


def _rows(entries, with_dates):
    meta = _read_meta() if with_dates else None
    out = []
    for e in entries:
        date = ""
        if with_dates:
            try:
                date = _date(_metadata(e["id"], meta)["upload_date"]) + "  "
            except Exception:
                date = "?           "
        views = f"{e['view_count']:,} views" if e.get("view_count") else ""
        out.append(f"{date}{e['id']}  [{_mmss(e.get('duration'))}]  "
                   f"{e.get('title')}  ({views})".replace("  ()", ""))
    if with_dates:
        _write_meta(meta)
    return out


def _search_channel(channel, query, limit):
    url = _channel_url(channel) + "/search?query=" + query.replace(" ", "+")
    with _ydl(playlistend=limit * 2) as y:
        info = y.extract_info(url, download=False)
    return _videos_only(info.get("entries"))[:limit]


# -------------------------------------------------------------------- tools

@mcp.tool()
def channel_videos(channel: str, limit: int = 25, query: str = "",
                   with_dates: bool = False) -> str:
    """A channel's uploads, newest first, or its search results for `query`.

    `channel` is '@handle', a channel URL, a UC... channel id, or the name of
    a watched channel. with_dates fetches each video's upload date (one extra
    request per video not already cached), so keep `limit` small with it.
    Pass a returned id to video_transcript to read the video."""
    base = _channel_url(channel)
    if query:
        entries = _search_channel(channel, query, limit)
        head = f"{base} — search {query!r}: {len(entries)} videos (search order)"
    else:
        with _ydl(playlistend=limit) as y:
            info = y.extract_info(base + "/videos", download=False)
        entries = _videos_only(info.get("entries"))[:limit]
        head = f"{info.get('channel') or base} — latest {len(entries)} uploads"
    return "\n".join([head, *_rows(entries, with_dates)])


@mcp.tool()
def search_youtube(query: str, limit: int = 10, channel: str = "",
                   with_dates: bool = False) -> str:
    """Search all of YouTube, or only `channel` if given. Results come in
    YouTube's relevance order and include each video's channel."""
    if channel:
        return channel_videos(channel, limit=limit, query=query,
                              with_dates=with_dates)
    with _ydl() as y:
        info = y.extract_info(f"ytsearch{limit}:{query}", download=False)
    entries = _videos_only(info.get("entries"))
    rows = _rows(entries, with_dates)
    return "\n".join([f"search {query!r}: {len(rows)} videos"] + [
        f"{r}  — {e.get('channel')}" for r, e in zip(rows, entries)])


@mcp.tool()
def player_videos(player_name: str, per_channel: int = 8,
                  with_dates: bool = True) -> str:
    """Search every watched channel for one player; only videos whose title
    carries the player's surname are kept, since a channel search for
    'Jayden Daniels' also returns other Jaydens. Dates are on by default:
    an injury breakdown from last season is a different injury."""
    surname = player_name.split()[-1].lower()
    chans = _read_channels()
    if not chans:
        return "No watched channels; add one with watch_channel."
    out = []
    for ch in chans:
        try:
            hits = [e for e in _search_channel(ch["handle"], player_name,
                                               per_channel * 2)
                    if surname in (e.get("title") or "").lower()][:per_channel]
        except Exception as ex:
            out.append(f"{ch['name']}: search failed ({ex})")
            continue
        out.append(f"{ch['name']} ({ch['handle']}): {len(hits)} videos")
        out.extend("  " + r for r in _rows(hits, with_dates))
    return "\n".join(out)


@mcp.tool()
def video_transcript(url_or_id: str, timestamps: bool = False,
                     max_chars: int = 40000) -> str:
    """Transcript of one video, headed by its title, channel, upload date and
    the first lines of its description.

    Uses the uploaded English captions if there are any, else YouTube's
    auto-generated ones (which misspell names and medical terms: 'olecranon'
    comes out as 'electronon'). timestamps=True prefixes a [m:ss] marker
    about every 30 seconds, to point back at a moment in the video."""
    vid = _video_id(url_or_id)
    TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
    path = TRANSCRIPTS / f"{vid}.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi()
        listing = api.list(vid)
        try:
            tr = listing.find_manually_created_transcript(["en", "en-US", "en-GB"])
        except Exception:
            tr = listing.find_generated_transcript(["en", "en-US", "en-GB"])
        fetched = tr.fetch()
        data = {"language": tr.language, "generated": tr.is_generated,
                "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "snippets": [[round(s.start, 1), s.text] for s in fetched]}
        path.write_text(json.dumps(data), encoding="utf-8")

    try:
        m = _metadata(vid)
        head = [f"{m['title']}",
                f"{m['channel']} ({m['handle']}) · uploaded {_date(m['upload_date'])}"
                f" · {_mmss(m['duration'])} · https://youtu.be/{vid}"]
        desc = " ".join((m.get("description") or "").split())[:300]
        if desc:
            head.append(f"description: {desc}")
    except Exception as ex:
        head = [f"https://youtu.be/{vid} (metadata unavailable: {ex})"]
    head.append(f"captions: {data['language']}"
                + ("" if data["generated"] else ", uploaded by the creator"))

    if timestamps:
        parts, mark = [], -30.0
        for start, text in data["snippets"]:
            if start - mark >= 30:
                parts.append(f"\n[{_mmss(start) if start >= 1 else '0:00'}]")
                mark = start
            parts.append(text)
        body = " ".join(parts).strip()
    else:
        body = " ".join(t for _, t in data["snippets"])
    if len(body) > max_chars:
        body = body[:max_chars] + f"\n… truncated at {max_chars} chars"
    return "\n".join(head) + "\n\n" + body


@mcp.tool()
def watched_channels() -> str:
    """The channels player_videos searches, with why each is on the list."""
    chans = _read_channels()
    if not chans:
        return "No watched channels."
    return "\n".join(f"{c['name']}  {c['handle']}  — {c.get('note', '')}"
                     for c in chans)


@mcp.tool()
def watch_channel(channel: str, note: str = "", remove: bool = False) -> str:
    """Add a channel to channels.json (or remove it). `channel` is '@handle'
    or a channel URL; its display name is looked up. The file is committed,
    so the list follows the repo to the other machine."""
    chans = _read_channels()
    if remove:
        key = channel.strip().lstrip("@").lower()
        kept = [c for c in chans
                if key not in (c["handle"].lstrip("@").lower(), c["name"].lower())]
        CHANNELS.write_text(json.dumps(kept, indent=2) + "\n", encoding="utf-8")
        return f"removed {len(chans) - len(kept)} channel(s)"
    base = _channel_url(channel)
    with _ydl(playlistend=1) as y:
        info = y.extract_info(base + "/videos", download=False)
    handle = info.get("uploader_id") or "@" + base.rsplit("@", 1)[-1]
    if any(c["handle"].lower() == handle.lower() for c in chans):
        return f"{handle} is already watched"
    chans.append({"name": info.get("channel") or handle, "handle": handle,
                  "channel_id": info.get("channel_id"), "note": note})
    CHANNELS.write_text(json.dumps(chans, indent=2) + "\n", encoding="utf-8")
    return f"watching {chans[-1]['name']} ({handle})"


if __name__ == "__main__":
    mcp.run()
