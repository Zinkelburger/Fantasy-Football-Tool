"""Reproducible temporal holdout and matched-file comparison, no network.

Run with the league-sim Python: audit_public_scores.py --downloads DIR.
Only aggregate results and source hashes are saved; source tables stay local.
"""
import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import polars as pl

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'engine/weekly'))
import ep_model
import nfl_data


def norm(name):
    name = re.sub(r'\s*\([^)]*\)', '', name)
    name = re.sub(r"[.'’\-]", '', name).lower()
    key = re.sub(r'\s+(jr|sr|ii|iii|iv|v)$', '', name).replace(' ', '')
    # Verified display-name variants in the cached nflverse player records.
    return {'kennethgainwell':'kennygainwell','joshuapalmer':'joshpalmer',
            'drewogletree':'andrewogletree'}.get(key,key)


def correlation(x, y):
    return float(np.corrcoef(x, y)[0, 1]) if len(x) > 2 and np.std(x) and np.std(y) else None


def metrics(x, y):
    x, y = np.asarray(x), np.asarray(y)
    return {'r': correlation(x, y), 'mae': float(np.mean(abs(x-y))),
            'rmse': float(np.sqrt(np.mean((x-y)**2))), 'bias': float(np.mean(x-y))}


def fit_predict(train, test, pos, features, fmt='half'):
    coef = ep_model._fit(train, features, 'pts_' + fmt)
    return np.maximum(0, ep_model.predict(test, {'coef': {pos: {fmt: coef}},
                      'features': {pos: features}}, pos, fmt))


def bootstrap_delta(rows, repeats=1000):
    """Paired MAE difference (ours minus theirs), resampling whole players."""
    groups = {}
    for r in rows:
        groups.setdefault(r['player'], []).append(abs(r['ours']-r['actual'])-abs(r['theirs']-r['actual']))
    vals = list(groups.values())
    sums = np.array([sum(v) for v in vals]); counts = np.array([len(v) for v in vals])
    rng = np.random.default_rng(39)
    estimates = []
    for _ in range(repeats):
        ix = rng.integers(0, len(vals), len(vals))
        estimates.append(float(sums[ix].sum()/counts[ix].sum()))
    return {'ours_minus_theirs_mae': float(sums.sum()/counts.sum()),
            'player_bootstrap_95pct': np.quantile(estimates, [.025, .975]).tolist()}


def run(downloads):
    panels = {y: ep_model.panel(y, False) for y in range(2021, 2026)}
    # A candidate using completed air yards helps distinguish description from
    # opportunity. It is a proxy for the author's YBC, not his exact algorithm.
    for y in panels:
        p = nfl_data.pbp(y, False).filter((pl.col('season_type') == 'REG') &
             (pl.col('complete_pass') == 1) & pl.col('receiver_player_id').is_not_null())
        ybc = p.group_by(['season', 'week', 'receiver_player_id']).agg(pl.col('air_yards').fill_null(0).sum().alias('completed_air'))
        panels[y] = panels[y].join(ybc, left_on=['season','week','player_id'],
            right_on=['season','week','receiver_player_id'], how='left').with_columns(pl.col('completed_air').fill_null(0))
    result = {'method': 'Temporal holdout. Fit only years before the evaluated season. Half PPR. Matched player-weeks. Next calendar week uses only earlier matched games (up to four).',
              'sources': [], 'comparisons': [], 'holdout2025': []}
    shipped = ep_model.load_coef()
    for year in (2024, 2025):
        train_all = pl.concat([v for y, v in panels.items() if y < year])
        for pos in ('QB','RB','WR','TE'):
            train = train_all.filter(pl.col('position') == pos)
            test = panels[year].filter(pl.col('position') == pos)
            pred = fit_predict(train, test, pos, ep_model.FEATURES[pos])
            if year == 2025:
                for fmt in ('half','half6'):
                    pred_fmt = fit_predict(train, test, pos, ep_model.FEATURES[pos], fmt)
                    m = metrics(pred_fmt, test['pts_'+fmt].to_numpy())
                    result['holdout2025'].append({'position':pos,'format':fmt,'n':len(test),
                        'r2': ep_model._r2(test['pts_'+fmt].to_numpy(),pred_fmt), **m})
            if pos == 'QB':
                continue
            path = downloads / f'{year} Opportunity Score - {pos}.csv'
            result['sources'].append({'file': path.name, 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
            simple = ['rush_att','rush_i10','tgt','tgt_i10'] if pos == 'RB' else ['rush_att','tgt','tgt_rz','completed_air']
            simple_pred = fit_predict(train, test, pos, simple)
            current = np.maximum(0, ep_model.predict(test, shipped, pos, 'half'))
            index = {}
            for i, r in enumerate(test.iter_rows(named=True)):
                key = (norm(r['name']),r['week'])
                if key in index:
                    raise ValueError(f'Ambiguous player/week: {key}')
                index[key] = {**r,'ours':float(pred[i]),'candidate':float(simple_pred[i]),'shipped':float(current[i])}
            matched, unmatched, zero_without_usage = [], [], 0
            for r in csv.DictReader(path.open()):
                if not r['Player']: continue
                for col, v in r.items():
                    m = re.fullmatch(r'Week(\d+)',col or '')
                    if not m or v in ('','BYE',None): continue
                    try: value=float(v)
                    except ValueError: continue
                    key=(norm(r['Player']),int(m[1]))
                    if key not in index:
                        if value==0: zero_without_usage+=1
                        else: unmatched.append({'player':r['Player'],'week':key[1]})
                        continue
                    matched.append({**index[key],'theirs':value,'player':key[0]})
            actual=[r['pts_half'] for r in matched]
            same={k:metrics([r[k] for r in matched],actual) for k in ('ours','theirs','candidate','shipped')}
            history={}
            next_rows=[]
            for r in sorted(matched,key=lambda r:r['week']):
                history.setdefault(r['player'],[]).append(r)
                prev=history[r['player']][-4:]
                nxt=index.get((r['player'],r['week']+1))
                if nxt:
                    next_rows.append({'player':r['player'],'actual':nxt['pts_half'],
                        **{k:float(np.mean([h[k] for h in prev])) for k in ('ours','theirs','candidate')},
                        'box_score':float(np.mean([h['pts_half'] for h in prev]))})
            next_metrics={k:metrics([r[k] for r in next_rows],[r['actual'] for r in next_rows]) for k in ('ours','theirs','candidate','box_score')}
            result['comparisons'].append({'season':year,'position':pos,'n':len(matched),
                'weeks':sorted({r['week'] for r in matched}), 'unmatched':unmatched,
                'zero_without_usage':zero_without_usage,
                'agreement_shipped':correlation([r['shipped'] for r in matched],[r['theirs'] for r in matched]),
                'same_game':same,'next_week_n':len(next_rows),'next_week':next_metrics,
                'next_week_paired_mae':bootstrap_delta(next_rows),
                'candidate': 'Four-input RB usage' if pos=='RB' else 'Four-input receiver model with completed air yards (YBC proxy)'})
    return result


if __name__ == '__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--downloads',type=Path,default=Path.home()/'Downloads')
    ap.add_argument('--output',type=Path,default=ROOT/'research/opportunity-score/audit-2026-09-15.json')
    args=ap.parse_args()
    output=run(args.downloads)
    args.output.write_text(json.dumps(output,indent=2)+'\n')
    for r in output['comparisons']:
        print(r['season'],r['position'],'matched',r['n'],'agreement',round(r['agreement_shipped'],3),
              'next-week MAE', {k:round(v['mae'],3) for k,v in r['next_week'].items()},r['next_week_paired_mae'])
