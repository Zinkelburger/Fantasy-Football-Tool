"""Weather for any place and for every NFL game, by the hour.

Two free sources, neither needs a key:

  NWS (api.weather.gov)   the official US hourly forecast, about 7 days out.
                          Used first for a US point inside that range.
  Open-Meteo              worldwide, 16 days out, plus past hours (recent
                          past from the forecast API, older from its archive).
                          Used abroad, beyond the NWS range, when NWS fails,
                          and for turning a place name into coordinates.

Venues come from stadiums.json (committed), keyed by the nflverse
stadium_id, so a game's coordinates, time zone and roof are looked up, never
geocoded. Lookups that do not change are cached on disk under cache/
(gitignored): place-name geocodes and the NWS grid for each point. Forecasts
are cached on disk for FORECAST_TTL and carry their actual retrieval time.

Nothing here feeds a projection. Weather is context for the reader; the
kicker and defense rankings do not use it (see finding 27).
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CACHE = HERE / "cache"
STADIUMS = HERE / "stadiums.json"
UA = "ff-weather (Fantasy-Football-Tool; personal use)"
ET = ZoneInfo("America/New_York")
UTC = timezone.utc

FORECAST_TTL = 20 * 60          # seconds a fetched forecast is reused
NWS_DAYS = 6.5                  # NWS hourly covers ~156 h; stay inside it
OM_FORECAST_DAYS = 16           # Open-Meteo forecast horizon
OM_PAST_DAYS = 80               # older than this goes to the archive API
GAME_HOURS = 3.5                # kickoff to final whistle, roughly

# Flags are for reading, not a model adjustment.
WIND_MPH, GUST_MPH = 15, 25
RAIN_PCT, RAIN_IN = 50, 0.10
COLD_F, HOT_F = 32, 90

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}

# WMO weather codes (Open-Meteo), shortened.
WMO = {
    0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Cloudy",
    45: "Fog", 48: "Freezing fog", 51: "Light drizzle", 53: "Drizzle",
    55: "Heavy drizzle", 56: "Freezing drizzle", 57: "Freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain",
    67: "Freezing rain", 71: "Light snow", 73: "Snow", 75: "Heavy snow",
    77: "Snow grains", 80: "Rain showers", 81: "Rain showers",
    82: "Violent rain showers", 85: "Snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm, hail", 99: "Thunderstorm, hail",
}


# ------------------------------------------------------------------ http
def _get_json(url: str, params: dict | None = None, timeout: int = 20) -> dict:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/geo+json, application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _disk(name: str) -> dict:
    p = CACHE / name
    return json.loads(p.read_text()) if p.exists() else {}


def _disk_put(name: str, key: str, value) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    d = _disk(name)
    d[key] = value
    (CACHE / name).write_text(json.dumps(d, indent=1, sort_keys=True))


def _memo(key: tuple, fn, refresh=False):
    from evidence_cache import EvidenceCache  # weekly path initialized below

    def fetch():
        value = fn()
        return {**value, "rows": [{**r, "t": r["t"].isoformat()} for r in value["rows"]]}

    result = EvidenceCache(CACHE / "forecasts.sqlite3").read(
        ["forecast-v1", *map(str, key)], fetch, FORECAST_TTL, refresh=refresh)
    if result["data"] is None:
        raise RuntimeError(result["retrieval"].get("error", "Forecast unavailable"))
    value = result["data"]
    return {**value, "rows": [{**r, "t": datetime.fromisoformat(r["t"])} for r in value["rows"]],
            "retrieval": result["retrieval"]}


def _retrieval_label(data):
    r = data.get("retrieval")
    if not r:
        return ""
    return (f"; retrieved {r['fetched_at']}; cache_hit={r['cache_hit']}; "
            f"age {r['age_seconds']}s; expires {r['expires_at']}")


# ------------------------------------------------------------------ venues
@lru_cache(maxsize=1)
def stadiums() -> dict[str, dict]:
    return json.loads(STADIUMS.read_text())["stadiums"]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _team_names() -> dict[str, str]:
    """nickname (normalised) -> abbreviation, from the weekly engine."""
    try:
        from common import TEAMS  # engine/weekly
    except ImportError:
        return {}
    return {_norm(v): k for k, v in TEAMS.items()}


def find_stadium(query: str) -> tuple[str, dict] | None:
    """A venue by stadium_id, team (GB, Packers), or stadium name/alias."""
    q = query.strip()
    if not q:
        return None
    st = stadiums()
    if q.upper() in st:
        return q.upper(), st[q.upper()]
    abbr = q.upper() if len(q) <= 3 else _team_names().get(_norm(q))
    if abbr:
        for sid, s in st.items():
            if abbr in s["home"]:
                return sid, s
    nq = _norm(q)
    if len(nq) < 4:
        return None
    for sid, s in st.items():
        if any(nq == _norm(n) for n in [s["name"], *s["aliases"]]):
            return sid, s
    for sid, s in st.items():
        if any(nq in _norm(n) for n in [s["name"], *s["aliases"]]):
            return sid, s
    return None


def venue_for_game(stadium_id: str | None, stadium_name: str | None,
                   home: str) -> tuple[str, dict] | None:
    """The venue for a schedule row. The name wins over the id, because
    nflverse has reused a team's id for its London game (JAX00 labelled
    Tottenham Hotspur Stadium in 2026); then the id; then the home team's
    usual stadium."""
    st = stadiums()
    if stadium_name:
        nn = _norm(stadium_name)
        for sid, s in st.items():
            if any(nn == _norm(n) for n in [s["name"], *s["aliases"]]):
                return sid, s
    if stadium_id and stadium_id in st:
        return stadium_id, st[stadium_id]
    return find_stadium(home)


def is_us(tz: str | None, country_code: str | None = None) -> bool:
    if country_code:
        return country_code.upper() == "US"
    return bool(tz) and (tz.startswith("America/") or tz.startswith("Pacific/Honolulu")) \
        and tz not in ("America/Mexico_City", "America/Sao_Paulo", "America/Toronto")


# ------------------------------------------------------------------ places
def resolve_place(place: str) -> dict:
    """{name, lat, lon, tz, us, stadium_id?} for a stadium, a team, "lat,lon",
    or a place name ("Green Bay, WI", "London", "Buffalo NY")."""
    m = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*", place)
    if m:
        lat, lon = float(m.group(1)), float(m.group(2))
        return {"name": f"{lat:.4f}, {lon:.4f}", "lat": lat, "lon": lon,
                "tz": None, "us": None}
    hit = find_stadium(place)
    if hit:
        sid, s = hit
        return {"name": f"{s['name']} ({s['city']})", "lat": s["lat"],
                "lon": s["lon"], "tz": s["tz"], "us": is_us(s["tz"]),
                "stadium_id": sid, "roof": s["roof"]}
    return geocode(place)


def geocode(place: str) -> dict:
    key = place.strip().lower()
    cached = _disk("geocode.json").get(key)
    if cached:
        return cached
    parts = [p.strip() for p in re.split(r",", place) if p.strip()]
    name, qual = parts[0], " ".join(parts[1:])
    if not qual:   # "Buffalo NY"
        m = re.fullmatch(r"(.+?)\s+([A-Za-z]{2})", name)
        if m and m.group(2).upper() in US_STATES:
            name, qual = m.group(1), m.group(2)
    res = _get_json("https://geocoding-api.open-meteo.com/v1/search",
                    {"name": name, "count": 20, "language": "en", "format": "json"})
    results = res.get("results") or []
    if not results:
        raise ValueError(f"no place found for {place!r}")
    pick = results[0]
    if qual:
        want = {qual.lower(), US_STATES.get(qual.upper(), "").lower()} - {""}
        for r in results:
            fields = {str(r.get(k, "")).lower() for k in
                      ("admin1", "admin2", "country", "country_code")}
            if want & fields:
                pick = r
                break
    label = ", ".join(x for x in (pick.get("name"), pick.get("admin1"),
                                  pick.get("country_code")) if x)
    out = {"name": label, "lat": pick["latitude"], "lon": pick["longitude"],
           "tz": pick.get("timezone"), "us": pick.get("country_code") == "US"}
    _disk_put("geocode.json", key, out)
    return out


# ------------------------------------------------------------------ sources
def _nws_hourly_url(lat: float, lon: float) -> str | None:
    """The NWS hourly endpoint for a point, or None outside NWS coverage.
    Grid assignments do not move, so both answers are cached on disk."""
    key = f"{lat:.4f},{lon:.4f}"
    grid = _disk("nws_points.json")
    if key in grid:
        return grid[key]
    try:
        p = _get_json(f"https://api.weather.gov/points/{key}")
        url = p["properties"]["forecastHourly"]
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        url = None
    _disk_put("nws_points.json", key, url)
    return url


def _mph(s) -> float | None:
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", str(s or ""))]
    return max(nums) if nums else None


def nws_hours(lat: float, lon: float, refresh: bool = False) -> dict:
    url = _nws_hourly_url(lat, lon)
    if not url:
        raise LookupError("point is outside NWS coverage")

    def fetch():
        d = _get_json(url)
        rows = []
        for p in d["properties"]["periods"]:
            t = p["temperature"]
            if p.get("temperatureUnit") == "C":
                t = t * 9 / 5 + 32
            rows.append({
                "t": datetime.fromisoformat(p["startTime"]).astimezone(UTC),
                "temp_f": t, "wind_mph": _mph(p.get("windSpeed")),
                "wind_dir": p.get("windDirection") or "",
                "gust_mph": _mph(p.get("windGust")),
                "precip_pct": (p.get("probabilityOfPrecipitation") or {}).get("value") or 0,
                "precip_in": None, "sky": p.get("shortForecast", "")})
        return {"rows": rows, "issued": d["properties"].get("updateTime")
                or d["properties"].get("generatedAt")}
    return _memo(("nws", url), fetch, refresh)


def _compass(deg) -> str:
    if deg is None:
        return ""
    pts = "N NNE NE ENE E ESE SE SSE S SSW SW WSW W WNW NW NNW".split()
    return pts[int((deg % 360) / 22.5 + 0.5) % 16]


def open_meteo_hours(lat: float, lon: float, start: date, end: date, refresh: bool = False) -> dict:
    today = datetime.now(UTC).date()
    archive = end < today - timedelta(days=OM_PAST_DAYS)
    base = ("https://archive-api.open-meteo.com/v1/archive" if archive
            else "https://api.open-meteo.com/v1/forecast")
    hourly = ["temperature_2m", "precipitation", "wind_speed_10m",
              "wind_direction_10m", "wind_gusts_10m", "weather_code"]
    if not archive:
        hourly.insert(1, "precipitation_probability")
    params = {"latitude": lat, "longitude": lon, "hourly": ",".join(hourly),
              "temperature_unit": "fahrenheit", "wind_speed_unit": "mph",
              "precipitation_unit": "inch", "timezone": "GMT",
              "start_date": start.isoformat(), "end_date": end.isoformat()}

    def fetch():
        d = _get_json(base, params)
        h = d["hourly"]
        rows = []
        for i, ts in enumerate(h["time"]):
            code = h["weather_code"][i]
            rows.append({
                "t": datetime.fromisoformat(ts).replace(tzinfo=UTC),
                "temp_f": h["temperature_2m"][i], "wind_mph": h["wind_speed_10m"][i],
                "wind_dir": _compass(h["wind_direction_10m"][i]),
                "gust_mph": h["wind_gusts_10m"][i],
                "precip_pct": (h.get("precipitation_probability") or [None] * len(h["time"]))[i],
                "precip_in": h["precipitation"][i],
                "sky": WMO.get(code, f"code {code}") if code is not None else ""})
        kind = ("archive (observed reanalysis)" if archive
                else "past hours (model analysis)" if end < today else "forecast")
        return {"rows": rows, "issued": None, "kind": kind}
    return _memo(("om", base, lat, lon, start, end), fetch, refresh)


def hours(lat: float, lon: float, start: datetime, end: datetime,
          us: bool | None, source: str = "auto", refresh: bool = False) -> tuple[str, str | None, list[dict]]:
    """Hourly rows covering [start, end) (aware datetimes) and the source
    used. auto: NWS for a US point inside its range, else Open-Meteo."""
    now = datetime.now(UTC)
    nws_ok = (source in ("auto", "nws") and us is not False
              and start >= now - timedelta(hours=1)
              and end <= now + timedelta(days=NWS_DAYS))
    errors = []
    if nws_ok:
        try:
            d = nws_hours(lat, lon, refresh=refresh)
            rows = [r for r in d["rows"] if start - timedelta(hours=1) < r["t"] < end]
            if rows and rows[0]["t"] <= start + timedelta(minutes=59):
                return "NWS hourly forecast" + _retrieval_label(d), d["issued"], rows
            errors.append("NWS: window not covered")
        except Exception as e:  # noqa: BLE001 - fall back to Open-Meteo
            errors.append(f"NWS: {e}")
    if source == "nws":
        raise RuntimeError("; ".join(errors) or "NWS not available for this point/time")
    if start.date() > (now + timedelta(days=OM_FORECAST_DAYS - 1)).date():
        raise LookupError(f"beyond the {OM_FORECAST_DAYS}-day forecast horizon")
    d = open_meteo_hours(lat, lon, start.astimezone(UTC).date(),
                         end.astimezone(UTC).date(), refresh=refresh)
    rows = [r for r in d["rows"] if start - timedelta(hours=1) < r["t"] < end]
    label = f"Open-Meteo {d['kind']}"
    if errors and source == "auto" and nws_ok:
        label += f" (fell back: {errors[-1]})"
    return label + _retrieval_label(d), d["issued"], rows


# ------------------------------------------------------------------ summary
def summarise(rows: list[dict]) -> dict:
    def mx(k):
        v = [r[k] for r in rows if r.get(k) is not None]
        return max(v) if v else None
    temps = [r["temp_f"] for r in rows if r.get("temp_f") is not None]
    amounts = [r["precip_in"] for r in rows if r.get("precip_in") is not None]
    s = {"temp_lo": min(temps) if temps else None, "temp_hi": max(temps) if temps else None,
         "wind_max": mx("wind_mph"), "gust_max": mx("gust_mph"),
         "precip_pct_max": mx("precip_pct"),
         "precip_in": round(sum(amounts), 2) if amounts else None}
    flags = []
    if (s["wind_max"] or 0) >= WIND_MPH:
        flags.append(f"wind {s['wind_max']:.0f} mph")
    if (s["gust_max"] or 0) >= GUST_MPH:
        flags.append(f"gusts {s['gust_max']:.0f} mph")
    if (s["precip_pct_max"] or 0) >= RAIN_PCT or (s["precip_in"] or 0) >= RAIN_IN:
        flags.append("precipitation likely")
    if s["temp_lo"] is not None and s["temp_lo"] <= COLD_F:
        flags.append(f"freezing ({s['temp_lo']:.0f}F)")
    if s["temp_hi"] is not None and s["temp_hi"] >= HOT_F:
        flags.append(f"heat ({s['temp_hi']:.0f}F)")
    s["flags"] = flags
    return s


def fmt_summary(s: dict) -> str:
    def n(v, unit="", nd=0):
        return "?" if v is None else f"{v:.{nd}f}{unit}"
    temp = (n(s["temp_hi"], "F") if s["temp_lo"] is None or round(s["temp_lo"]) == round(s["temp_hi"])
            else f"{n(s['temp_hi'])}->{n(s['temp_lo'], 'F')}")
    parts = [temp, f"wind <={n(s['wind_max'], ' mph')}"]
    if s["gust_max"] is not None:
        parts.append(f"gusts <={n(s['gust_max'], ' mph')}")
    if s["precip_pct_max"] is not None:
        parts.append(f"rain chance <={n(s['precip_pct_max'], '%')}")
    if s["precip_in"] is not None:
        parts.append(f"{n(s['precip_in'], ' in', 2)} total")
    return ", ".join(parts)


def fmt_rows(rows: list[dict], tz: ZoneInfo, step: int = 1) -> list[str]:
    out = ["time             temp  wind         gust  rain%  in    sky"]
    for r in rows[::step]:
        t = r["t"].astimezone(tz).strftime("%a %m-%d %H:%M")
        gust = "" if r["gust_mph"] is None else f"{r['gust_mph']:.0f}"
        pct = "" if r["precip_pct"] is None else f"{r['precip_pct']:.0f}"
        amt = "" if r["precip_in"] is None else f"{r['precip_in']:.2f}"
        wind = f"{r['wind_mph'] or 0:.0f} {r['wind_dir']}".strip()
        out.append(f"{t}  {r['temp_f']:>4.0f}  {wind:<11}  {gust:>4}  {pct:>5}  "
                   f"{amt:>4}  {r['sky']}")
    return out


# ------------------------------------------------------------------ schedule
def _weekly():
    """Make engine/weekly importable (season/week state, cached schedule)."""
    w = str(ROOT / "engine" / "weekly")
    if w not in sys.path:
        sys.path.append(w)   # after our own dir: both have an mcp_server.py


_weekly()


def current_week() -> tuple[int, int]:
    from common import nfl_state
    st = nfl_state()
    return st["season"], st["week"]


def week_games(season: int, week: int) -> list[dict]:
    """One dict per game: teams, kickoff (aware, from the schedule's ET
    gametime), venue id and entry. Reads the nflverse schedule the weekly
    engine already caches."""
    import nfl_data
    import polars as pl
    df = nfl_data.schedules(season).filter(pl.col("week") == week)
    games = []
    for g in df.iter_rows(named=True):
        kick = datetime.fromisoformat(f"{g['gameday']}T{g['gametime'] or '13:00'}").replace(tzinfo=ET)
        v = venue_for_game(g.get("stadium_id"), g.get("stadium"), g["home_team"])
        games.append({"away": g["away_team"], "home": g["home_team"], "kickoff": kick,
                      "neutral": g.get("location") == "Neutral",
                      "venue_id": v[0] if v else None, "venue": v[1] if v else None,
                      "raw_stadium": g.get("stadium")})
    games.sort(key=lambda x: (x["kickoff"], x["home"]))
    return games
