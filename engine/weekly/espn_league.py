"""ESPN fantasy league client: read rosters, free agents, matchups and
projections; write lineup changes and add/drop transactions.

Credentials (engine/weekly/.env, or engine/league-sim/.env):
  ESPN_LEAGUE_ID   the league (Sumfun League = 112618)
  ESPN_S2, ESPN_SWID   your espn.com cookies (private league + any write)
  ESPN_TEAM_ID     optional; otherwise found from SWID in the members list

Reads go to lm-api-reads.fantasy.espn.com, writes to
lm-api-writes.fantasy.espn.com, same paths. Every write goes through
`transaction()` which refuses to send unless dry_run=False AND the
caller passes the exact proposal it previewed (see mcp_server.py), so
an agent cannot skip the "do you want to drop X for Y?" step.

Transaction payload shapes are the ones the ESPN web client sends
(also used by ffscrapr and the espn-api community); a lineup move is
type ROSTER with LINEUP items, an add/drop is FREEAGENT (or WAIVER when
the player is on waivers) with ADD/DROP items.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from common import (ESPN_POSITIONS, ESPN_PRO_TEAMS, ESPN_SLOTS,
                    NON_STARTING_SLOTS, load_env, now_iso)

READ = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl"
WRITE = "https://lm-api-writes.fantasy.espn.com/apis/v3/games/ffl"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")

INJURY_MULT = {  # share of a normal projection an injury designation leaves
    "ACTIVE": 1.0, "PROBABLE": 0.95, "QUESTIONABLE": 0.8, "DOUBTFUL": 0.15,
    "OUT": 0.0, "INJURY_RESERVE": 0.0, "SUSPENSION": 0.0, "DAY_TO_DAY": 0.9,
}


def _r(v):
    return round(v, 2) if v is not None else None


class EspnError(RuntimeError):
    pass


class League:
    def __init__(self, season: int, env: dict | None = None):
        env = env or load_env()
        self.season = season
        self.league_id = env.get("ESPN_LEAGUE_ID")
        if not self.league_id:
            raise EspnError("ESPN_LEAGUE_ID is not set (engine/weekly/.env)")
        self.swid = env.get("ESPN_SWID") or ""
        self.s2 = env.get("ESPN_S2") or ""
        self.team_id = int(env["ESPN_TEAM_ID"]) if env.get("ESPN_TEAM_ID") else None
        self._settings = None

    # ---------------------------------------------------------------- http
    def _headers(self, extra: dict | None = None) -> dict:
        h = {"User-Agent": UA, "Accept": "application/json"}
        if self.s2 and self.swid:
            h["Cookie"] = f"espn_s2={self.s2}; SWID={self.swid}"
        h.update(extra or {})
        return h

    def _url(self, base: str, views: list[str], extra: str = "") -> str:
        q = "&".join(f"view={v}" for v in views)
        return (f"{base}/seasons/{self.season}/segments/0/leagues/"
                f"{self.league_id}?{q}{extra}")

    def get(self, views: list[str], extra: str = "", headers: dict | None = None):
        req = urllib.request.Request(self._url(READ, views, extra),
                                     headers=self._headers(headers))
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise EspnError("ESPN refused the request: this is a private "
                                "league, set ESPN_S2 and ESPN_SWID in "
                                "engine/weekly/.env") from e
            raise

    def post(self, path: str, body: dict) -> dict:
        if not (self.s2 and self.swid):
            raise EspnError("writes need ESPN_S2 and ESPN_SWID")
        url = f"{WRITE}/seasons/{self.season}/segments/0/leagues/{self.league_id}{path}"
        data = json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, method="POST", headers=self._headers({
            "Content-Type": "application/json",
            "X-Fantasy-Source": "kona", "X-Fantasy-Platform": "kona-PROD",
            "Origin": "https://fantasy.espn.com",
            "Referer": "https://fantasy.espn.com/"}))
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read().decode()
                return json.loads(raw) if raw else {"status": r.status}
        except urllib.error.HTTPError as e:
            raise EspnError(f"ESPN write failed HTTP {e.code}: {e.read().decode()[:500]}") from e

    # ------------------------------------------------------------ settings
    def settings(self) -> dict:
        if self._settings is None:
            d = self.get(["mSettings", "mTeam"])
            s = d["settings"]
            slots = {int(k): v for k, v in s["rosterSettings"]["lineupSlotCounts"].items() if v}
            items = {i["statId"]: i["points"] for i in s["scoringSettings"]["scoringItems"]}
            rec = items.get(53, 0.0)
            fmt = "ppr" if rec >= 1 else "half" if rec >= 0.5 else "std"
            members = {m["id"]: m.get("displayName") for m in d.get("members", [])}
            teams = []
            for t in d["teams"]:
                teams.append({"id": t["id"], "name": t.get("name") or f"{t.get('location','')} {t.get('nickname','')}".strip(),
                              "owners": t.get("owners", []),
                              "record": t.get("record", {}).get("overall", {})})
            my = self.team_id
            if my is None and self.swid:
                for t in teams:
                    if self.swid in t["owners"]:
                        my = t["id"]
            self._settings = {
                "league": s.get("name"), "season": self.season,
                "current_week": d.get("scoringPeriodId"),
                "matchup_period": d.get("status", {}).get("currentMatchupPeriod"),
                "slots": slots, "scoring_format": fmt,
                "scoring_items": items, "teams": teams, "members": members,
                "my_team_id": my,
                "waiver_type": s.get("acquisitionSettings", {}).get("acquisitionType"),
                "waiver_order_reset": s.get("acquisitionSettings", {}).get("waiverOrderReset"),
                "trade_deadline": s.get("tradeSettings", {}).get("deadlineDate"),
                "fetched": now_iso(),
            }
        return self._settings

    # -------------------------------------------------------------- roster
    @staticmethod
    def _stat(player: dict, week: int, source: int) -> float | None:
        """statSourceId 0 = actual, 1 = ESPN projection; split 1 = week."""
        for s in player.get("stats", []):
            if (s.get("scoringPeriodId") == week and s.get("statSourceId") == source
                    and s.get("statSplitTypeId") == 1):
                return s.get("appliedTotal")
        return None

    def _player(self, entry: dict, week: int) -> dict:
        pp = entry.get("playerPoolEntry") or entry
        p = pp["player"]
        inj = p.get("injuryStatus", "ACTIVE") if p.get("injured") or p.get("injuryStatus") else "ACTIVE"
        own = p.get("ownership", {})
        return {
            "id": p["id"], "name": p["fullName"],
            "pos": ESPN_POSITIONS.get(p.get("defaultPositionId"), "?"),
            "team": ESPN_PRO_TEAMS.get(p.get("proTeamId")),
            "eligible_slots": [s for s in p.get("eligibleSlots", []) if s in ESPN_SLOTS],
            "slot": entry.get("lineupSlotId"),
            "slot_name": ESPN_SLOTS.get(entry.get("lineupSlotId")),
            "injury": inj or "ACTIVE",
            "injury_mult": INJURY_MULT.get(inj or "ACTIVE", 1.0),
            "espn_proj": _r(self._stat(p, week, 1)),
            "espn_actual": _r(self._stat(p, week, 0)),
            "locked": bool(pp.get("lineupLocked") or pp.get("rosterLocked")),
            "pct_owned": round(own.get("percentOwned", 0.0), 1),
            "pct_started": round(own.get("percentStarted", 0.0), 1),
            "pct_change": round(own.get("percentChange", 0.0), 1),
            "on_team_id": pp.get("onTeamId"),
            "status": pp.get("status"),
            "acquisition": entry.get("acquisitionType"),
        }

    def rosters(self, week: int) -> dict[int, list[dict]]:
        d = self.get(["mRoster", "mTeam"], f"&scoringPeriodId={week}")
        out = {}
        for t in d["teams"]:
            out[t["id"]] = [self._player(e, week) for e in t.get("roster", {}).get("entries", [])]
        return out

    def my_roster(self, week: int) -> list[dict]:
        s = self.settings()
        if s["my_team_id"] is None:
            raise EspnError("cannot tell which team is yours: set ESPN_TEAM_ID "
                            "(see `teams` in league settings)")
        return self.rosters(week)[s["my_team_id"]]

    def matchup(self, week: int) -> dict | None:
        """My matchup this week: opponent team id/name and both scores."""
        s = self.settings()
        d = self.get(["mMatchupScore", "mTeam"], f"&scoringPeriodId={week}")
        names = {t["id"]: t["name"] for t in s["teams"]}
        for m in d.get("schedule", []):
            if m.get("matchupPeriodId") != (s.get("matchup_period") or week):
                continue
            sides = {k: m[k] for k in ("home", "away") if k in m}
            ids = {k: v["teamId"] for k, v in sides.items()}
            if s["my_team_id"] in ids.values():
                me = "home" if ids.get("home") == s["my_team_id"] else "away"
                opp = "away" if me == "home" else "home"
                return {"week": week, "opponent_id": ids.get(opp),
                        "opponent": names.get(ids.get(opp)),
                        "my_points": sides[me].get("totalPoints"),
                        "opp_points": sides.get(opp, {}).get("totalPoints"),
                        "my_projected": sides[me].get("totalProjectedPointsLive"),
                        "opp_projected": sides.get(opp, {}).get("totalProjectedPointsLive")}
        return None

    def free_agents(self, week: int, positions: list[str] | None = None,
                    limit: int = 300) -> list[dict]:
        pos_ids = [k for k, v in ESPN_POSITIONS.items() if not positions or v in positions]
        filt = {"players": {
            "filterStatus": {"value": ["FREEAGENT", "WAIVERS"]},
            "filterSlotIds": {"value": [0, 2, 4, 6, 16, 17, 23]},
            "limit": limit, "offset": 0,
            "sortPercOwned": {"sortAsc": False, "sortPriority": 1},
            "filterRanksForScoringPeriodIds": {"value": [week]},
            "filterStatsForCurrentSeasonScoringPeriodId": {"value": [week]},
        }}
        if positions:
            filt["players"]["filterPositionIds"] = {"value": pos_ids}
        d = self.get(["kona_player_info"], f"&scoringPeriodId={week}",
                     headers={"X-Fantasy-Filter": json.dumps(filt)})
        out = []
        for pp in d.get("players", []):
            row = self._player({"playerPoolEntry": pp, "lineupSlotId": None}, week)
            row["waiver"] = pp.get("status") == "WAIVERS"
            out.append(row)
        return out

    # -------------------------------------------------------------- writes
    def transaction(self, kind: str, items: list[dict], week: int,
                    dry_run: bool = True, bid: int | None = None) -> dict:
        s = self.settings()
        body = {"isLeagueManager": False, "teamId": s["my_team_id"],
                "type": kind, "memberId": self.swid, "scoringPeriodId": week,
                "executionType": "EXECUTE", "items": items}
        if bid is not None:
            body["bidAmount"] = bid
        if dry_run:
            return {"dry_run": True, "would_post": body}
        return {"dry_run": False, "response": self.post("/transactions/", body),
                "posted": body}

    def set_lineup(self, moves: list[dict], week: int, dry_run: bool = True) -> dict:
        """moves: [{player_id, from_slot, to_slot}, ...] applied as one
        ROSTER transaction (ESPN validates the whole lineup at once)."""
        items = [{"playerId": m["player_id"], "type": "LINEUP",
                  "fromLineupSlotId": m["from_slot"], "toLineupSlotId": m["to_slot"]}
                 for m in moves]
        return self.transaction("ROSTER", items, week, dry_run)

    def add_drop(self, add_id: int, drop_id: int | None, week: int,
                 waiver: bool = False, bid: int | None = None,
                 dry_run: bool = True) -> dict:
        s = self.settings()
        items = [{"playerId": add_id, "type": "ADD", "toTeamId": s["my_team_id"]}]
        if drop_id is not None:
            items.append({"playerId": drop_id, "type": "DROP", "fromTeamId": s["my_team_id"]})
        return self.transaction("WAIVER" if waiver else "FREEAGENT", items, week,
                                dry_run, bid=bid)


def starting_slots(settings: dict) -> dict[int, int]:
    return {k: v for k, v in settings["slots"].items() if k not in NON_STARTING_SLOTS}
