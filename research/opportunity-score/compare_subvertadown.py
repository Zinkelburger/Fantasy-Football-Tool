"""Compare our per-game expected points with Subvertadown's published
weekly opportunity scores (finding 39, "vs Subvertadown's published scores").

    .venv-league-sim/bin/python research/opportunity-score/compare_subvertadown.py DIR

DIR holds his CSV exports named like "2025 Opportunity Score - RB.csv"
(Rank, Player, Week1..WeekN, ...). They are his data and are not committed.
Needs the cached play-by-play for the seasons compared (engine/weekly/cache).
"""
import csv, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'engine' / 'weekly'))
import numpy as np, polars as pl
import opportunity

DL = Path(sys.argv[1] if len(sys.argv) > 1 else Path.home() / 'Downloads')
def norm(n):
    n = n.split(' (')[0]
    n = re.sub(r"[.'’\-]", '', n).lower()
    n = re.sub(r'\s+(jr|sr|ii|iii|iv)$', '', n)
    return n.replace(' ', '')

def read_sub(season, pos):
    rows = []
    with (DL / f'{season} Opportunity Score - {pos}.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            if not r['Player']:
                continue
            for k, v in r.items():
                m = re.match(r'Week(\d+)$', k or '')
                if not m or v in ('', 'BYE'):
                    continue
                try:
                    val = float(v)
                except ValueError:
                    continue
                if val == 0:
                    continue  # bye/DNP in 2024 files
                rows.append(dict(name=norm(r['Player']), raw=r['Player'], pos=pos, week=int(m.group(1)), sub=val))
    return rows

def corr(a, b):
    return float(np.corrcoef(a, b)[0, 1])

for season in (2024, 2025):
    ours = opportunity.season_ep(season, refresh=False)
    ours = ours.with_columns(pl.col('name').map_elements(norm, return_dtype=pl.Utf8).alias('key'))
    for pos in ('RB', 'WR', 'TE'):
        sub = pl.DataFrame(read_sub(season, pos))
        o = ours.filter(pl.col('position') == pos).select(['key', 'week', 'ep_std', 'ep_half', 'ep_ppr', 'pts_std', 'pts_half', 'pts_ppr'])
        j = sub.join(o, left_on=['name', 'week'], right_on=['key', 'week'], how='left')
        matched = j.filter(pl.col('ep_half').is_not_null())
        unmatched = j.filter(pl.col('ep_half').is_null())['raw'].unique().to_list()
        m = matched
        s = m['sub'].to_numpy()
        line = [f'{season} {pos}: {m.height} player-weeks matched, {len(unmatched)} names unmatched']
        for fmt in ('std', 'half', 'ppr'):
            e = m[f'ep_{fmt}'].to_numpy(); p = m[f'pts_{fmt}'].to_numpy()
            slope, icpt = np.polyfit(e, s, 1)
            line.append(f'  {fmt}: r(sub, ours)={corr(s, e):.3f}  r(sub, actual)={corr(s, p):.3f}  r(ours, actual)={corr(e, p):.3f}  mean sub {s.mean():.1f} ours {e.mean():.1f}  slope {slope:.2f}')
        # season level: per player mean
        g = m.group_by('name').agg([pl.len().alias('n'), pl.col('sub').mean(), pl.col('ep_half').mean(), pl.col('pts_half').mean()]).filter(pl.col('n') >= 8)
        line.append(f'  season (8+ wks, n={g.height}): r(sub, ours)={corr(g["sub"].to_numpy(), g["ep_half"].to_numpy()):.3f}  r(sub, actual)={corr(g["sub"].to_numpy(), g["pts_half"].to_numpy()):.3f}  r(ours, actual)={corr(g["ep_half"].to_numpy(), g["pts_half"].to_numpy()):.3f}')
        # next-week: his last-4 avg vs next week's actual, ours same
        print('\n'.join(line))
        if unmatched[:8]:
            print('  unmatched e.g.:', unmatched[:8])
