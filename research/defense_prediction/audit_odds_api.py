"""Offline coverage audit of saved Odds API snapshots. No API requests/credits.

Run from repo root: python3 research/defense_prediction/audit_odds_api.py
Uses same-book paired spread/total, with both market timestamps preserved.
"""
import csv
import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'engine/weekly'))
from common import TEAMS

CACHE = ROOT / 'engine/weekly/cache/odds-api-audit'
OUT = Path(__file__).resolve().parent / 'reports/2026-09-14'


def team(name):
    matches = [abbr for abbr, nickname in TEAMS.items() if name.endswith(' ' + nickname)]
    if len(matches) != 1:
        raise ValueError(f'Unknown/ambiguous team: {name}')
    return matches[0]


def pairs(event):
    """Reject incomplete/cross-book pairs and inconsistent outcome lines."""
    result = []
    for book in event.get('bookmakers', []):
        markets = {m['key']: m for m in book.get('markets', [])}
        spread, total = markets.get('spreads', {}), markets.get('totals', {})
        s = {o['name']: o.get('point') for o in spread.get('outcomes', [])}
        t = {o['name']: o.get('point') for o in total.get('outcomes', [])}
        vals = [s.get(event['home_team']), s.get(event['away_team']), t.get('Over'), t.get('Under')]
        if any(not isinstance(v, (float, int)) or not math.isfinite(v) for v in vals):
            continue
        hs, aws, over, under = vals
        if abs(hs + aws) > 1e-8 or over != under or over <= abs(hs):
            continue
        result.append(dict(book=book['key'], homeSpread=hs, total=over,
                           homePoints=(over-hs)/2, awayPoints=(over+hs)/2,
                           spreadUpdated=spread.get('last_update', book.get('last_update')),
                           totalUpdated=total.get('last_update', book.get('last_update'))))
    return result


def main():
    schedule = list(csv.DictReader((ROOT/'engine/weekly/cache/nfelo-audit/games.csv').open()))
    games = [g for g in schedule if g['season'] == '2026' and g['game_type'] == 'REG']
    lookup = {(g['gameday'], g['away_team'], g['home_team']): g for g in games}
    assert len(lookup) == 272
    # Latest snapshot per query, not a blend of observations at different times.
    files = [sorted(CACHE.glob('*'+suffix))[-1] for suffix in
             ('-sports.json', '-nfl-odds.json', '-nfl-events.json', '-nfl-other-regions.json')]
    sources, rows = [], []
    for path in files:
        snap = json.loads(path.read_text())
        src = {k: snap[k] for k in ('fetched_at', 'endpoint', 'params', 'usage')}
        src.update(file=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                   events=len(snap['data']))
        coverage = Counter()
        if not path.name.endswith('-sports.json'):
            for e in snap['data']:
                date = datetime.fromisoformat(e['commence_time'].replace('Z','+00:00')).astimezone(ZoneInfo('America/New_York')).date().isoformat()
                g = lookup[(date, team(e['away_team']), team(e['home_team']))]
                coverage[int(g['week'])] += 1
                if not path.name.endswith('-nfl-odds.json'):
                    continue
                assert datetime.fromisoformat(e['commence_time'].replace('Z','+00:00')) > datetime.fromisoformat(snap['fetched_at'])
                paired = pairs(e)
                if not paired:
                    continue
                rows.append(dict(gameId=g['game_id'], week=int(g['week']),
                    home=g['home_team'], away=g['away_team'], kickoff=e['commence_time'],
                    fetchedAt=snap['fetched_at'], books=paired,
                    homeOpponentPoints=median(b['awayPoints'] for b in paired),
                    awayOpponentPoints=median(b['homePoints'] for b in paired)))
        src['weeks'] = dict(sorted(coverage.items()))
        sources.append(src)
    assert len({r['gameId'] for r in rows}) == len(rows)
    defenses = [dict(team=r[side], opponent=r[other], week=r['week'], gameId=r['gameId'],
                     opponentPoints=r[side+'OpponentPoints'], books=len(r['books']))
                for r in rows for side, other in [('home','away'),('away','home')]]
    defenses.sort(key=lambda r: (r['week'], r['opponentPoints'], r['team']))
    for r in defenses:
        r['rank'] = 1 + sum(x['week']==r['week'] and x['opponentPoints']<r['opponentPoints'] for x in defenses)
    report = dict(sources=sources, games=rows, defenses=defenses,
                  method='Median of same-book opponent implied points; sportsbook spread sign. Equal totals share rank. US region only for ranking; other regions audited for coverage.',
                  limitation='Market-implied NFL points are neither exact expected scores nor D/ST fantasy projections. Coverage is observed at retrieval, not a future availability guarantee.')
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'odds-api-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'sources':sources, 'week2Top': [r for r in defenses if r['week']==2][:8]}, indent=2))


if __name__ == '__main__':
    main()
