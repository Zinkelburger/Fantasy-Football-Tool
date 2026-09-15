"""Public player play logs from the same cached PBP used for opportunities.

No live requests. Structured participant IDs determine inclusion; names in
descriptions are never guessed. Keep context plays distinct from model usage.
"""
from __future__ import annotations

import json
from collections import defaultdict

import polars as pl

from common import DATA

PARTICIPANTS = {
    'passer_player_id': 'pass', 'receiver_player_id': 'target',
    'rusher_player_id': 'run', 'lateral_receiver_player_id': 'lateral catch',
    'lateral_rusher_player_id': 'lateral run',
    'punt_returner_player_id': 'punt return',
    'kickoff_returner_player_id': 'kickoff return',
    'fumbled_1_player_id': 'fumble', 'fumbled_2_player_id': 'fumble',
    'penalty_player_id': 'penalty',
}


def number(value):
    return None if value is None else int(value) if float(value).is_integer() else float(value)


def summarize(r, roles):
    """Only label outcomes supported by explicit source fields."""
    no_play = r.get('play_type') == 'no_play'
    flags = []
    if no_play:
        flags.append('No play')
    if r.get('penalty') == 1:
        flags.append('Penalty')
    if r.get('two_point_attempt') == 1:
        flags.append('2-point attempt')
    if 'fumble' in roles:
        flags.append('Fumble')
    yards = None
    if r.get('qb_kneel') == 1 and 'run' in roles:
        label, kind = 'Kneel-down', 'other'
    elif r.get('qb_spike') == 1 and 'pass' in roles:
        label, kind = 'Spike', 'pass'
    elif r.get('sack') == 1 and 'pass' in roles:
        yards = number(r.get('yards_gained'))
        label, kind = 'Sacked', 'other'
    elif 'run' in roles:
        yards = number(r.get('rushing_yards'))
        label, kind = 'Run', 'run'
        if r.get('qb_scramble') == 1:
            label = 'Scramble'
    elif 'pass' in roles or 'target' in roles:
        passing = 'pass' in roles
        kind = 'pass' if passing else 'target'
        if r.get('interception') == 1:
            label = 'Intercepted pass' if passing else 'Target intercepted'
        elif r.get('complete_pass') == 1:
            label = 'Completed pass' if passing else 'Catch'
            yards = number(r.get('passing_yards' if passing else 'receiving_yards'))
        elif r.get('incomplete_pass') == 1:
            label = 'Incomplete pass' if passing else 'Incomplete target'
        else:
            label = 'Pass' if passing else 'Target'
    elif 'lateral catch' in roles or 'lateral run' in roles:
        receiving = 'lateral catch' in roles
        kind, label = 'other', 'Lateral catch' if receiving else 'Lateral run'
        yards = number(r.get('lateral_receiving_yards' if receiving else 'lateral_rushing_yards'))
    elif 'punt return' in roles or 'kickoff return' in roles:
        kind = 'other'
        label = 'Punt return' if 'punt return' in roles else 'Kickoff return'
        yards = number(r.get('return_yards'))
    else:
        kind, label = 'other', 'Penalty' if 'penalty' in roles else 'Fumble'
    if yards is not None:
        label = f'{yards}-yard {label.lower()}'
    if not no_play and (('pass' in roles and r.get('pass_touchdown') == 1)
                        or r.get('td_player_id') in [r.get(k) for k, role in PARTICIPANTS.items()
                                                    if role in roles and role not in ('pass', 'penalty', 'fumble')]
                        and r.get('td_player_id') is not None):
        flags.append('Touchdown')
    # Exactly the model's usage predicates; sacks/kneels/no-plays remain context.
    counts = []
    if r.get('play_type') in ('run', 'pass') and r.get('posteam') is not None:
        if 'run' in roles:
            counts.append('carry')
        if 'target' in roles and r.get('pass_attempt') == 1:
            counts.append('target')
        if 'pass' in roles and r.get('pass_attempt') == 1 and not r.get('sack'):
            counts.append('pass attempt')
    return label, kind, flags, counts


def build(pbp: pl.DataFrame, weekly: pl.DataFrame, season: int):
    eligible = set(weekly['player_id'].to_list())
    through_week = int(weekly['week'].max())
    players = defaultdict(lambda: {'weeks': {}})
    source = pbp.filter((pl.col('season_type') == 'REG') & (pl.col('week') <= through_week))
    source = source.sort(['week', 'game_id', 'play_id'])
    seen = set()
    for r in source.iter_rows(named=True):
        key = (r['game_id'], r['play_id'])
        if key in seen:
            raise ValueError(f'Duplicate source play: {key}')
        seen.add(key)
        involved = defaultdict(list)
        for column, role in PARTICIPANTS.items():
            if r.get(column) in eligible and role not in involved[r[column]]:
                involved[r[column]].append(role)
        for pid, roles in involved.items():
            game = players[pid]['weeks'].setdefault(str(r['week']), {
                'gameId': r['game_id'], 'date': str(r.get('game_date') or ''),
                'away': r.get('away_team'), 'home': r.get('home_team'), 'plays': []})
            if game['gameId'] != r['game_id']:
                raise ValueError(f'Multiple games for player/week: {pid} / {r["week"]}')
            label, kind, flags, counts = summarize(r, roles)
            game['plays'].append({
                'id': number(r['play_id']), 'quarter': number(r.get('qtr')),
                'clock': r.get('time'), 'down': number(r.get('down')),
                'toGo': number(r.get('ydstogo')), 'field': r.get('yrdln'),
                'label': label, 'kind': kind, 'flags': flags, 'countsAs': counts,
                'airYards': number(r.get('air_yards')) if kind in ('pass', 'target') else None,
                'description': r.get('desc') or 'Description unavailable.',
            })
    return {'schemaVersion': 1, 'season': season, 'throughWeek': through_week,
            'source': 'nflverse play-by-play',
            'sourceUrl': 'https://nflreadr.nflverse.com/articles/dictionary_pbp.html',
            'players': dict(players)}


def write(pbp, weekly, season):
    payload = build(pbp, weekly, season)
    # Validate that the log can explain every displayed usage count before saving.
    for r in weekly.iter_rows(named=True):
        game = payload['players'].get(r['player_id'], {}).get('weeks', {}).get(str(r['week']))
        if not game:
            raise ValueError(f'Missing player play log: {r["player_id"]} / {r["week"]}')
        for field, label in [('rush_att', 'carry'), ('tgt', 'target'), ('pass_att', 'pass attempt')]:
            count = sum(label in p['countsAs'] for p in game['plays'])
            if count != r[field]:
                raise ValueError(f'Play log usage mismatch: {r["player_id"]} {field}: {count} != {r[field]}')
    (DATA / f'opportunity_{season}_plays.json').write_text(json.dumps(payload, separators=(',', ':'))+'\n')
    return payload
