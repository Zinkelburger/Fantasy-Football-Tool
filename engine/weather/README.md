# engine/weather — ff-weather MCP server

Hourly weather for any place, and for every NFL game at its own stadium.
No API keys. Registered in `.mcp.json` as `ff-weather`; the launcher uses the
weekly engine's venv (`.venv-league-sim`), because `game_weather` reads the
nflverse schedule that engine already caches.

| tool | what |
|---|---|
| `weather(place, start, hours, source)` | a city (`"Green Bay, WI"`, `"Buffalo NY"`, `"London"`), team (`GB`, `Packers`), stadium, or `"lat,lon"`; from now, a local date, or a local `"YYYY-MM-DD HH:MM"` |
| `game_weather(week, team)` | every game in the week (default current), kickoff to +3.5 h, with flags |
| `stadium(query)` | the venue map; no query lists every venue |

**Sources.** NWS (api.weather.gov) for US points inside about 6.5 days: the
official forecast. Open-Meteo for other locations, for forecasts up to 16 days
out, as a fallback when NWS fails, for past hours, and to turn place names into
coordinates. Every output names the source it used.

**Venues** are in `stadiums.json`, which is committed and keyed by the nflverse
`stadium_id`. Each entry has coordinates, time zone and roof type (`outdoor`,
`retractable` or `fixed`). Games are never geocoded. nflverse's own `roof`
column is empty for retractable roofs, and it wrongly lists Munich, Paris and
Melbourne as domes, so roof type is read only from this file. A schedule row's
stadium name takes precedence over its id, because nflverse has reused a
team's id for its London game. If a new venue appears, `game_weather` prints
"unmapped venue", and `test_cached_schedules_all_map` fails until you add it.

**Caching.** Place-name geocodes and the NWS grid for each point never
change, so they are stored in `cache/` (gitignored). Forecasts are cached in
memory for 20 minutes.

**Flags** mark wind of 15 mph or more, gusts of 25 mph or more, rain chance of
50% or more (or at least 0.10 in), temperatures at or below 32°F and at or
above 90°F. They are context for a person reading the output. No kicker,
defense or projection ranking in this repo adjusts for weather, and whether
it should would need its own study.

```
.venv-league-sim/bin/python -m unittest engine/weather/test_weather.py
```
