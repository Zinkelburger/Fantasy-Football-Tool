"""Temporal tests for advanced features. Run directly with the league-sim Python.

Frozen comparison: 2024 validation, 2025 confirmation; training only earlier
seasons. No random row split, no fitting on the evaluated year's outcomes.
The candidate changes each game's descriptive score, then the same production
EWMA (alpha .35, prior-season seed) turns it into a next-calendar-week forecast.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'engine/weekly'))
import advanced_usage
import ep_model
import nfl_data
import opportunity
from common import CACHE

YEARS = (2022, 2023, 2024, 2025)
EXTRAS = {
    'target_share': ['target_share'],
    'catchability': ['ftn_catchable_targets', 'catchable_rate'],
    'drops': ['ftn_drops', 'drop_rate'],
    'contact': ['pfr_yards_before_contact', 'ybc_per_carry'],
}
GATE = {'validation_and_confirmation_mae_gain': .05,
        'confirmation_bootstrap_upper_below': 0., 'max_rmse_regression': .02,
        'max_other_format_or_zero_usage_mae_regression': .02,
        'selection': 'Lowest 2024 half-PPR next-week EWMA MAE per position; baseline remains if gain <0.05. Only this selection is eligible on 2025.'}


def data_panel(year, ids):
    p, s = nfl_data.pbp(year), nfl_data.player_stats(year)
    f = pl.read_parquet(CACHE / f'ftn_{year}.parquet')
    r = pl.read_parquet(CACHE / f'pfr_rush_week_{year}.parquet')
    context = advanced_usage.build(p, s, f, r, ids)
    base = ep_model.panel(year)
    context = context.with_columns(
        (pl.col('ftn_catchable_targets') / pl.col('tgt')).alias('catchable_rate'),
        (pl.col('ftn_drops') / pl.col('tgt')).alias('drop_rate'),
        pl.when(pl.col('rush_att') > 0).then(pl.col('pfr_yards_before_contact') / pl.col('rush_att')).alias('ybc_per_carry'))
    fields = sorted({f for fs in EXTRAS.values() for f in fs})
    return base.join(context.select(*advanced_usage.KEY, *fields), on=advanced_usage.KEY, validate='1:1')


def design(train, test, fields):
    """Training-only mean imputation and explicit missing indicators."""
    a = train.select(fields).to_numpy().astype(float)
    b = test.select(fields).to_numpy().astype(float)
    am, bm = ~np.isfinite(a), ~np.isfinite(b)
    count = (~am).sum(axis=0)
    means = np.divide(np.where(am, 0, a).sum(axis=0), count,
                      out=np.zeros(len(fields)), where=count > 0)
    return (np.column_stack([np.ones(len(a)), np.where(am, means, a), am]),
            np.column_stack([np.ones(len(b)), np.where(bm, means, b), bm]))


def predict(train, test, fields, fmt):
    a, b = design(train, test, fields)
    beta = np.linalg.lstsq(a, train['pts_' + fmt].to_numpy(), rcond=None)[0]
    return np.maximum(0, b @ beta)


def metrics(pred, actual):
    e = np.asarray(pred) - np.asarray(actual)
    return {'n': len(e), 'mae': float(abs(e).mean()), 'rmse': float(np.sqrt((e*e).mean())), 'bias': float(e.mean())}


def ci_delta(ids, pred, base, actual):
    groups = {}
    for pid, d in zip(ids, abs(pred-actual)-abs(base-actual)):
        groups.setdefault(pid, []).append(d)
    sums = np.array([sum(v) for v in groups.values()]); counts = np.array([len(v) for v in groups.values()])
    rng = np.random.default_rng(916)
    ix = rng.integers(0, len(sums), size=(2000, len(sums)))
    draws = sums[ix].sum(axis=1) / counts[ix].sum(axis=1)
    return {'delta_mae': float(sums.sum()/counts.sum()), 'player_bootstrap_95pct': np.quantile(draws, [.025, .975]).tolist()}


def forecasts(test, pred, prev, prev_pred, pos, fmt, scheduled):
    """Uses only games <=w to predict w+1. Missing usage has a separate zero sensitivity."""
    prior = {}
    for r, value in zip(prev.iter_rows(named=True), prev_pred):
        prior.setdefault(r['player_id'], []).append(value)
    repl = opportunity.REPLACEMENT[pos] * opportunity.REPL_SCALE[fmt]
    seed = {pid: min(1, len(v)/4)*np.mean(v) + (1-min(1, len(v)/4))*repl for pid,v in prior.items()}
    lookup = {(r['player_id'], r['week']): r for r in test.iter_rows(named=True)}
    state, history, out = {}, {}, []
    for r, value in zip(test.iter_rows(named=True), pred):
        pid, w = r['player_id'], r['week']
        state[pid] = .35*value + .65*state.get(pid, seed.get(pid, repl))
        history.setdefault(pid, []).append(value)
        if (w+1, r['team']) not in scheduled:
            continue
        nxt = lookup.get((pid, w+1))
        # A different next-week team would not have been known from this row.
        if nxt and nxt['team'] != r['team']:
            continue
        out.append({'id': pid, 'week': w+1, 'observed': nxt is not None,
                    'actual': nxt['pts_' + fmt] if nxt else 0.,
                    'ewma': state[pid], 'last4': float(np.mean(history[pid][-4:]))})
    return out


def run():
    ids = pl.read_parquet(CACHE / 'pfr_ids.parquet')
    panels = {y: data_panel(y, ids).sort(['player_id','week']) for y in YEARS}
    result = {'protocol': __doc__, 'gate': GATE, 'candidate_features': EXTRAS,
              'scoring': ['std','half','ppr'], 'evaluations': [], 'decisions': [], 'sources': []}
    for path in sorted(CACHE.glob('*.parquet')):
        if any(path.name == f'{stem}_{y}.parquet' for y in YEARS for stem in ['pbp','player_stats','ftn','pfr_rush_week']) or path.name == 'pfr_ids.parquet':
            result['sources'].append({'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    for year in (2024, 2025):
        train_all = pl.concat([panels[y] for y in YEARS if y < year], how='diagonal_relaxed')
        p = nfl_data.pbp(year)
        scheduled = set()
        for r in p.filter(pl.col('season_type') == 'REG').select('week','home_team','away_team').unique().iter_rows(named=True):
            scheduled.update([(r['week'], r['home_team']), (r['week'], r['away_team'])])
        for pos in ('RB','WR','TE'):
            tr = train_all.filter(pl.col('position') == pos)
            te = panels[year].filter(pl.col('position') == pos)
            prev = panels[year-1].filter(pl.col('position') == pos)
            variants = {'baseline': []} | {k:v for k,v in EXTRAS.items() if k != 'contact' or pos == 'RB'}
            variants['combined'] = list(dict.fromkeys(f for fs in variants.values() for f in fs))
            for fmt in ('std','half','ppr'):
                baselines = None
                for label, extra in variants.items():
                    fields = ep_model.FEATURES[pos] + extra
                    pred = predict(tr, te, fields, fmt)
                    prev_pred = predict(tr, prev, fields, fmt)
                    forecasts_ = forecasts(te, pred, prev, prev_pred, pos, fmt, scheduled)
                    actual = np.array([r['actual'] for r in forecasts_])
                    ix = np.array([r['observed'] for r in forecasts_])
                    values = {k: np.array([r[k] for r in forecasts_]) for k in ('ewma','last4')}
                    if label == 'baseline':
                        baselines = values
                    row = {'year': year, 'position': pos, 'format': fmt, 'variant': label,
                           'train_n': tr.height, 'test_n': te.height,
                           'feature_coverage': {f: te[f].is_not_null().sum()/te.height for f in extra},
                           'same_game': metrics(pred, te['pts_'+fmt].to_numpy()),
                           'next_week': {k:metrics(v[ix],actual[ix]) for k,v in values.items()},
                           'zero_usage_sensitivity': {k:metrics(v,actual) for k,v in values.items()},
                           'missing_next_usage': int((~ix).sum()),
                           'paired_ewma': ci_delta(np.array([r['id'] for r in forecasts_])[ix], values['ewma'][ix], baselines['ewma'][ix], actual[ix])}
                    result['evaluations'].append(row)
                print(year,pos,fmt,'done',flush=True)
    def get(year,pos,fmt,variant):
        return next(r for r in result['evaluations'] if (r['year'],r['position'],r['format'],r['variant'])==(year,pos,fmt,variant))
    for pos in ('RB','WR','TE'):
        val = [r for r in result['evaluations'] if (r['year'],r['position'],r['format'])==(2024,pos,'half')]
        best = min(val,key=lambda r:r['next_week']['ewma']['mae'])
        name = best['variant']
        base = get(2024,pos,'half','baseline')
        gain = base['next_week']['ewma']['mae'] - best['next_week']['ewma']['mae']
        candidate = get(2025,pos,'half',name); cb = get(2025,pos,'half','baseline')
        reasons=[]
        if name == 'baseline' or gain < .05: reasons.append('No candidate improves validation MAE by 0.05 points')
        if cb['next_week']['ewma']['mae']-candidate['next_week']['ewma']['mae'] < .05: reasons.append('Confirmation MAE improvement below 0.05 points')
        if candidate['paired_ewma']['player_bootstrap_95pct'][1] >= 0: reasons.append('Confirmation paired interval includes no improvement')
        if candidate['next_week']['ewma']['rmse']-cb['next_week']['ewma']['rmse'] > .02: reasons.append('Confirmation RMSE regresses')
        for fmt in ('std','half','ppr'):
            r,b=get(2025,pos,fmt,name),get(2025,pos,fmt,'baseline')
            for population in ('next_week','zero_usage_sensitivity'):
                if r[population]['ewma']['mae']-b[population]['ewma']['mae'] > .02:
                    reasons.append(f'{fmt} {population} MAE regresses')
        result['decisions'].append({'position':pos,'validation_best':name,'validation_gain':gain,
            'confirmation_gain': cb['next_week']['ewma']['mae']-candidate['next_week']['ewma']['mae'],
            'adopt': not reasons, 'reasons':reasons})
    return result


if __name__ == '__main__':
    output = run()
    path = ROOT/'research/opportunity-score/advanced-model-audit-2026-09-16.json'
    path.write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    print(json.dumps(output['decisions'],indent=2))
