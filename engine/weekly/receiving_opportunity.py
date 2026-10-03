"""Bounded receiving-role evidence. No forecasts and no network in this module."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field


def norm(name: str) -> str:
    name = re.sub(r"[.'’]", "", name.casefold()).strip()
    return re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", name)


class Practice(BaseModel):
    designation: str = ""
    injury: str = ""
    days: dict[str, str] = Field(default_factory=dict)
    source: str | None = None


class Receiver(BaseModel):
    player_id: str = Field(description="Stable nflverse GSIS ID; not an ESPN transaction ID.")
    name: str
    position: str
    targets: list[float | None] = Field(max_length=6, description="Aligned with observed_weeks; null means no usage row, not confirmed inactive.")
    snap_share_pct: list[float | None] = Field(max_length=6, description="Aligned with observed_weeks, percentage 0–100; null means missing.")
    prior_target_share_pct: float | None = Field(description="Percentage 0–100: targets / all team targets in baseline_weeks; NOT restricted to games with a usage row.")
    latest_target_share_pct: float | None = Field(description="Percentage 0–100 in the latest observed game.")
    change_percentage_points: float | None
    signals: list[str] = Field(default_factory=list, description="Reasons to investigate; usage changes do not diagnose an injury.")
    practice: Practice | None = Field(default=None, description="Matching decision-week official row only. Null/blank does not mean cleared.")
    absence: Literal["reported_out", "uncertain", "not_established"] = "not_established"
    availability: Literal["free_agent", "waivers", "rostered", "unknown"] = "unknown"
    espn_id: int | None = None
    current_nfl_team: str | None = None
    fantasy_team_id: int | None = None


class ReceivingOpportunity(BaseModel):
    season: int
    decision_week: int
    team: str
    as_of: str
    decision_status: Literal["needs_injury_confirmation", "absence_reported", "usage_only", "data_incomplete"]
    next_step: str
    ordering: str = "Latest observed targets, then prior target share; NOT a pickup ranking."
    observed_weeks: list[int] = Field(max_length=6)
    team_targets: list[float] = Field(max_length=6)
    baseline_weeks: list[int] = Field(max_length=5, description="All observed weeks except the latest; not necessarily healthy games.")
    concern: Receiver | None = None
    candidates: list[Receiver] = Field(max_length=8, description="Other receivers by latest targets, then prior share; an evidence shortlist, not pickup rankings.")
    omitted_players: int
    practice_coverage: str
    practice_freshness: str
    practice_fetched_at: str | None = None
    league_status: Literal["live", "unavailable"]
    scoring_format: str | None = None
    notes: list[str]


def usage_rows(usage: list[dict], team: str, week: int, last: int,
               concern: str = "") -> tuple[list[int], list[float], list[Receiver], str | None]:
    """Pool denominators over the same team games; exclude decision/future weeks."""
    rows = [r for r in usage if r["team"] == team and int(r["week"]) < week]
    weeks = sorted({int(r["week"]) for r in rows})[-last:]
    if not weeks:
        raise ValueError("No prior team usage on file; refresh_week before evaluating receiving opportunity.")
    selected = [r for r in rows if int(r["week"]) in weeks]
    totals = {}
    players = {}
    for r in selected:
        w = int(r["week"])
        total = float(r["team_targets"])
        if w in totals and totals[w] != total:
            raise ValueError("Conflicting team target totals; refresh saved usage before comparing shares.")
        totals[w] = total
        if r["position"] in {"WR", "TE", "RB"}:
            players.setdefault(r["player_id"], {})[w] = r
    prior_total = sum(totals[w] for w in weeks[:-1])
    out = []
    for pid, games in players.items():
        latest = games[max(games)]
        targets = [float(games[w]["tgt"]) if w in games else None for w in weeks]
        snaps = [float(games[w]["snap_share"]) if w in games and
                 games[w].get("snap_share") not in (None, "") else None for w in weeks]
        if not any(targets) and norm(latest["name"]) != norm(concern):
            continue
        prior = sum(t or 0 for t in targets[:-1]) / prior_total if prior_total else None
        # No row means no recorded targets, but preserve the missing row in targets.
        share = (targets[-1] or 0) / totals[weeks[-1]] if totals[weeks[-1]] else None
        signals = []
        if prior is not None and prior >= .10:
            if targets[-1] is None:
                signals.append("no usage row in latest game; verify absence")
            prior_snaps = [s for s in snaps[:-1] if s is not None]
            if snaps[-1] is not None and prior_snaps and sum(prior_snaps) / len(prior_snaps) - snaps[-1] >= .20:
                signals.append("snap share fell at least 20 percentage points; check injury/role reporting")
        out.append(Receiver(
            player_id=pid, name=latest["name"], position=latest["position"],
            targets=targets, snap_share_pct=[round(s * 100, 2) if s is not None else None for s in snaps],
            prior_target_share_pct=round(prior * 100, 2) if prior is not None else None,
            latest_target_share_pct=round(share * 100, 2) if share is not None else None,
            change_percentage_points=round(100 * (share - prior), 2)
            if share is not None and prior is not None else None, signals=signals))
    focus = [r for r in out if norm(r.name) == norm(concern)] if concern else []
    if concern and len(focus) != 1:
        raise ValueError("concern must match one full player name in this team's observed usage; use player_lookup/depth_chart to resolve it.")
    out.sort(key=lambda r: (-(r.targets[-1] or 0), -(r.prior_target_share_pct or 0), r.name))
    return weeks, [totals[w] for w in weeks], out, focus[0].player_id if focus else None


def attach_practice(rows: list[Receiver], evidence: dict, season: int, week: int, team: str) -> None:
    """Never promote stale, mismatched or historical designations to current absence."""
    report = evidence.get("report") or {}
    usable = (evidence.get("season"), evidence.get("week"), evidence.get("team")) == (season, week, team)
    usable = usable and (evidence.get("retrieval") or {}).get("status") == "fresh"
    usable = usable and (report.get("coverage") or {}).get("status") == "available"
    if not usable:
        return
    for row in rows:
        hits = [r for r in report.get("rows", []) if norm(r.get("player", "")) == norm(row.name)
                and r.get("week") == week and r.get("team") == team]
        if len(hits) != 1:
            continue
        hit = hits[0]
        row.practice = Practice(designation=hit.get("game_status") or "", injury=hit.get("injury") or "",
                                days={d: hit.get(d) or "" for d in (hit.get("practice_days") or "").split(",") if d},
                                source=hit.get("source"))
        status = row.practice.designation.casefold()
        row.absence = "reported_out" if status == "out" else "uncertain" if status in {"questionable", "doubtful"} else "not_established"


def attach_availability(rows: list[Receiver], pool: list[dict], crosswalk: dict[str, str]) -> None:
    """Stable IDs first; exact unique name+position fallback. Never substring join."""
    for row in rows:
        hits = [p for p in pool if crosswalk.get(str(p["id"])) == row.player_id]
        if not hits:
            hits = [p for p in pool if not crosswalk.get(str(p["id"]))
                    and norm(p["name"]) == norm(row.name) and p["pos"] == row.position]
        unique = {p["id"]: p for p in hits}
        if len(unique) != 1:
            continue
        p = next(iter(unique.values()))
        row.espn_id, row.current_nfl_team = p["id"], p.get("team")
        row.fantasy_team_id = p.get("on_team_id") or None
        if row.fantasy_team_id:
            row.availability = "rostered"
        elif p.get("status") == "WAIVERS":
            row.availability = "waivers"
        elif p.get("status") == "FREEAGENT":
            row.availability = "free_agent"
