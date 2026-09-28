# engine/youtube — YouTube as a source

The `ff-youtube` MCP server reads YouTube without an API key: a channel's
uploads, search, and video transcripts. It exists for injury-analysis
channels. A sports-medicine doctor going through the replay usually says
more about how long a player will be out than the team's first injury
report does.

Claude Code starts it from `.mcp.json` via `engine/mcp_launch.sh youtube`,
which uses `.venv-youtube` at the repo root (or `engine/youtube/.venv`) and
builds it from `requirements.txt` if neither exists. A cold build can outlast
Claude Code's ~30s startup wait, so on a new machine run
`engine/mcp_launch.sh setup youtube` once, or reconnect with `/mcp`.

| tool | what |
|---|---|
| `channel_videos` | a channel's latest uploads, or `query=` to search inside it |
| `search_youtube` | YouTube-wide search, or pass `channel=` to limit it to one channel |
| `player_videos` | searches every watched channel for a player and keeps only titles with their surname, with upload dates |
| `video_transcript` | the transcript, headed by the title, channel, upload date and description; `timestamps=True` for [m:ss] markers |
| `watched_channels` / `watch_channel` | the list in `channels.json` (committed) |

Listings and metadata come from yt-dlp. Transcripts come from
youtube-transcript-api, because yt-dlp's subtitle download gets HTTP 429
from YouTube. Flat listings have no upload dates, so `with_dates` makes one
request per video. Each date is cached in `cache/meta.json` and never
fetched twice.

Transcripts are cached in `cache/transcripts/`, which is gitignored.
The text is the creator's work: summarise it, and don't commit it or put
it on the site. Auto-generated captions misspell names and medical terms
("electronon" for olecranon), so check a name before you act on it.
