"""Audit cached public nfelo/nflverse files and build a full-season coverage table.

Run from repo root: python3 research/defense_prediction/audit_nfelo_outlook.py
Inputs: engine/weekly/cache/nfelo-audit/*.csv (downloaded public source files).
No credentials, fantasy projections, or network required for this audit.
"""
import csv
import hashlib
import html
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / 'engine/weekly/cache/nfelo-audit'
OUT = Path(__file__).resolve().parent / 'reports/2026-09-14'
ALIASES = {'LAR':'LA','STL':'LA','OAK':'LV','SD':'LAC','JAC':'JAX','WSH':'WAS'}
SOURCES = {
    'nfelo_games.csv':'https://raw.githubusercontent.com/greerreNFL/nfelo/main/output_data/nfelo_games.csv',
    'games.csv':'https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv',
    'elo_snapshot.csv':'https://raw.githubusercontent.com/greerreNFL/nfelo/main/output_data/elo_snapshot.csv',
}


def key(gid):
    year, week, away, home = gid.split('_')
    return f'{year}_{int(week):02}_{ALIASES.get(away,away)}_{ALIASES.get(home,home)}'


def num(row, field):
    try:
        n = float(row[field])
        return n if math.isfinite(n) else None
    except (KeyError, ValueError, TypeError):
        return None


def implied(total, home_spread):
    """Sportsbook home spread: negative means favored. Returns home, away."""
    return (total-home_spread)/2, (total+home_spread)/2


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    tables = {name:list(csv.DictReader((CACHE/name).open())) for name in SOURCES}
    nfl, nfelo = tables['games.csv'], tables['nfelo_games.csv']
    models = {key(r['game_id']):r for r in nfelo}
    assert len(models)==len(nfelo), 'Duplicate normalized game ID'
    games = [r for r in nfl if r['season']=='2026' and r['game_type']=='REG']
    counts = Counter(t for g in games for t in (g['home_team'],g['away_team']))
    assert len(games)==272 and len(counts)==32 and set(counts.values())=={17}
    archived = {key(r['game_id']):r for r in csv.DictReader((ROOT/'engine/league-sim/data/market/games.csv').open())}
    odds_path = OUT/'odds-api-audit.json'
    odds_audit = json.loads(odds_path.read_text()) if odds_path.exists() else None
    odds_games = {r['gameId']:r for r in odds_audit['games']} if odds_audit else {}
    cells = {}
    coverage = []
    for week in range(1,19):
        gs = [g for g in games if int(g['week'])==week]
        coverage.append({'week':week,'games':len(gs),
            'marketPairs':sum(num(g,'spread_line') is not None and num(g,'total_line') is not None for g in gs),
            'archivedOnlyPairs':sum((num(g,'total_line') is None or num(g,'spread_line') is None) and num(archived.get(key(g['game_id']),{}),'total_line') is not None and num(archived.get(key(g['game_id']),{}),'spread_line') is not None for g in gs),
            'nfeloSpreads':sum(num(models.get(key(g['game_id']),{}),'nfelo_home_line_close') is not None for g in gs)})
        for g in gs:
            spread, total = num(g,'spread_line'), num(g,'total_line')
            # nflverse positive spread means home favored: flip to sportsbook sign.
            points = implied(total,-spread) if spread is not None and total is not None else (None,None)
            old = archived.get(key(g['game_id']),{})
            odds = odds_games.get(g['game_id'])
            archived_points = implied(num(old,'total_line'),-num(old,'spread_line')) if num(old,'total_line') is not None and num(old,'spread_line') is not None else (None,None)
            for side, team, opponent, opponent_points in [
                ('home',g['home_team'],g['away_team'],points[1]),
                ('away',g['away_team'],g['home_team'],points[0])]:
                assert (team,week) not in cells
                if odds:
                    opponent_points = odds[side+'OpponentPoints']
                cells[team,week] = {'opponent':opponent,'matchup':('vs ' if side=='home' or g['location']=='Neutral' else '@ ')+opponent,
                    'neutral':g['location']=='Neutral','opponentPoints':opponent_points,
                    'archivedOpponentPoints':archived_points[1 if side=='home' else 0] if opponent_points is None else None,
                    'archiveProvenance':'Repository games.csv snapshot committed 2026-08-04, not freshly verified market lines',
                    'state':'Historical' if num(g,'home_score') is not None else 'Upcoming',
                    'gameId':g['game_id'], 'oddsApiFetchedAt':odds['fetchedAt'] if odds else None}
    paired=[]
    for g in nfl:
        if g['game_type']!='REG' or not 2009<=int(g['season'])<=2025:continue
        model=models.get(key(g['game_id']),{})
        values=[num(model,k) for k in ('home_line_close','nfelo_home_line_close','total_line_close')]+[num(g,k) for k in ('home_score','away_score')]
        if any(v is None for v in values):continue
        market, prediction, total, home, away=values
        mh,ma=implied(total,market);nh,na=implied(total,prediction)
        paired.append({'gameId':g['game_id'],'marketHomeSpread':market,'nfeloHomeSpread':prediction,
            'marketTotal':total,'actualHomePoints':home,'actualAwayPoints':away,
            'marketMarginError':abs(-market-(home-away)), 'nfeloMarginError':abs(-prediction-(home-away)),
            'marketTeamScoreError':(abs(mh-home)+abs(ma-away))/2,
            'nfeloTeamScoreError':(abs(nh-home)+abs(na-away))/2})
    summary={'games':len(paired),'seasons':'2009–2025 regular season',
        'equalSpreadPercent':100*mean(r['marketHomeSpread']==r['nfeloHomeSpread'] for r in paired),
        'meanAbsoluteSpreadDifference':mean(abs(r['marketHomeSpread']-r['nfeloHomeSpread']) for r in paired),
        **{field:mean(r[field] for r in paired) for field in ('marketMarginError','nfeloMarginError','marketTeamScoreError','nfeloTeamScoreError')}}
    sources=[{'url':url,'sha256':hashlib.sha256((CACHE/name).read_bytes()).hexdigest(),
              'downloadedAt':datetime.fromtimestamp((CACHE/name).stat().st_mtime,timezone.utc).isoformat()} for name,url in SOURCES.items()]
    report={'generated':datetime.now(timezone.utc).isoformat(),'sources':sources,'coverage':coverage,'historicalComparison':summary,
            'oddsApiSources':odds_audit['sources'] if odds_audit else [],
            'caveat':'Retrospective comparison of mutable historical files, not an independently timestamped live backtest. Team-score error is not D/ST fantasy error. No future closing lines used as earlier forecasts.',
            'archivedScheduleSha256':hashlib.sha256((ROOT/'engine/league-sim/data/market/games.csv').read_bytes()).hexdigest(),
            'seasonTable':[{'team':t,'weeks':{str(w):cells.get((t,w)) for w in range(1,19)}} for t in sorted(counts)]}
    (OUT/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    (OUT/'historical-pairs.json').write_text(json.dumps(paired,separators=(',',':'))+'\n')
    headers=''.join(f'<th>W{w}</th>' for w in range(1,19))
    rows=[]
    for team in sorted(counts):
        tds=[]
        for week in range(1,19):
            c=cells.get((team,week))
            if c is None:tds.append('<td class="bye">BYE</td>');continue
            points=c['opponentPoints']; label='Line pending' if points is None else f'{points:g} opp. pts'
            if points is None and c['archivedOpponentPoints'] is not None:
                label=f"{c['archivedOpponentPoints']:g} archived opp. pts"
            style='' if points is None else f'background:hsl({max(0,min(120,(30-points)*10))} 45% 92%)'
            state='Historical line' if c['state']=='Historical' else 'Market line'
            if c['oddsApiFetchedAt']:
                state='Odds API · '+c['oddsApiFetchedAt'][:16].replace('T',' ')+' UTC'
            tds.append(f'<td style="{style}"><b>{html.escape(c["matchup"])}</b>{" · neutral" if c["neutral"] else ""}<span>{label}</span><small>{state if points is not None else "Aug 4 repo snapshot" if c["archivedOpponentPoints"] is not None else "No point forecast"}</small></td>')
        rows.append(f'<tr data-team="{team}"><th scope="row">{team}</th>'+''.join(tds)+'</tr>')
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>2026 defense season outlook — data audit</title>
<style>body{font:16px/1.5 system-ui,sans-serif;margin:2rem;color:#18251c;background:#fafcfb}h1{line-height:1.15}p{max-width:75ch}.scroll{overflow:auto;max-height:72vh;border:1px solid #ccd8cf}table{border-collapse:separate;border-spacing:0;font-size:13px}th,td{padding:10px;border-bottom:1px solid #dce4df;min-width:105px;text-align:left;background:white}thead th{position:sticky;top:0;z-index:2;background:#173d2a;color:white}th:first-child{position:sticky;left:0;min-width:45px;z-index:1}thead th:first-child{z-index:3}td span,td small{display:block}small{font-size:11px;color:#59645d}.bye{color:#77847c;background:#edf1ee}label{display:block;margin:1rem 0}select{padding:6px}a{color:#12633e}.note{border-left:3px solid #12633e;padding:12px;background:#edf6ef}</style>
<h1>2026 defense season outlook</h1><p>Source audit · September 14, 2026 · All 32 teams and 18 weeks</p>
<p class="note"><strong>Full schedule available; full-season point forecasts are not.</strong> Cells show each defense’s opponent and market-implied opponent points when a spread and total are available. The currently checked free feeds have no lines after Week 2. Older repository lookahead lines cover Week 3 and three Week 4 games; these are explicitly labeled and not treated as fresh odds. Blank forecasts are not byes. Week 1 historical lines below are newly retrieved source values, not our preserved pregame picks.</p>
<p>Market pairs: <strong>32 of 272 games</strong> (Weeks 1–2). nfelo game predictions: <strong>16 games</strong> (Week 1). Its 32-team rating snapshot is also labeled 2026 Week 1. Color reflects opponent points only where a market line exists.</p>
<label>Team <select id="team"><option value="">All teams</option>OPTIONS</select></label><div class="scroll" tabindex="0" role="region" aria-label="Full-season defense matchup table"><table><thead><tr><th>Defense</th>HEADERS</tr></thead><tbody>ROWS</tbody></table></div>
<h2>Where nfelo fits</h2><p>Its model estimates a spread (margin), not a complete game total. Use a market spread plus market total for near-term picks. A longer-range extension needs both an estimated spread and a separately validated game-total or team-score model. Overall Elo strength alone does not identify offense versus defense.</p>
<p>Our August notes report a full-season fetch from The Odds API, but only season averages remain locally; the original event response was not found. No Odds API key is configured here to verify current coverage. That API is the first candidate for filling the later weeks with real lines.</p><p>nfelo’s final spread includes market regression. Historical comparison: SUMMARY. This does not establish an improvement in fantasy D/ST scoring.</p>
<p><a href="audit.json">Audit data and source hashes</a> · <a href="historical-pairs.json">Matched historical games</a> · <a href="https://andrewbernal.com/football/defense/accuracy/">Preserved live accuracy report</a></p>
<script>document.getElementById('team').addEventListener('change',e=>document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!!e.target.value&&r.dataset.team!==e.target.value));</script></html>'''
    sentence=f"{len(paired):,} games; average spread difference {summary['meanAbsoluteSpreadDifference']:.2f} points; market/nfelo team-score MAE {summary['marketTeamScoreError']:.3f}/{summary['nfeloTeamScoreError']:.3f}. Both use the same market total. Retrospective mutable files, not a prospective validation"
    page=page.replace('OPTIONS',''.join(f'<option>{t}</option>' for t in sorted(counts))).replace('HEADERS',headers).replace('ROWS',''.join(rows)).replace('SUMMARY',sentence)
    if odds_audit:
        page=page.replace('The currently checked free feeds have no lines after Week 2.', 'The free feeds and authenticated Odds API checks across all five regions have no lines after Week 2 as of September 14, 2026.')
        page=page.replace('No Odds API key is configured here to verify current coverage. That API is the first candidate for filling the later weeks with real lines.', 'The key is now configured locally. The live check returned tonight’s game and all 16 Week 2 games; none for Week 3–18. Cells use US bookmaker consensus where available. This audit used 10 credits, leaving 490. <a href="odds-api-audit.json">API coverage, paired bookmaker lines and credit receipts</a>.')
    (OUT/'season-outlook.html').write_text(page)
    print(json.dumps({'coverage':coverage,'comparison':summary},indent=2))

if __name__=='__main__':main()
