"""Independent diagnostic fixed-source audit for both frozen sweep grids."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIXED = ('map_sha256', 'jurisdiction_sha256', 'fire_code_designation_sha256',
         'posting_authority_sha256', 'posted_extent_sha256',
         'sign_identity_sha256', 'sign_appearance_sha256',
         'curb_geometry_sha256', 'property_source_sha256',
         'one_way_source_sha256', 'route_sha256', 'weather_sha256',
         'camera_plan_sha256')


def load(case_id: str) -> dict:
    suffix = case_id.removeprefix(ROOT.name + '__')
    path = ROOT / ('diagnostic-' + suffix + '.json')
    spec = json.loads(path.read_text())
    site = json.loads(spec['files']['original-attempt/site.json'])
    rows = [json.loads(line) for line in
            spec['files']['original-attempt/history.jsonl'].splitlines()]
    return {'case_id': case_id, 'site': site, 'rows': rows,
            'fixture_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def audit(spec: dict, members: list[dict]) -> dict:
    if len(members) != spec['planned_case_count'] or len(members) < 3:
        raise ValueError('frozen sweep member count changed')
    first = members[0]['site']
    axis = spec['axes'][0]
    name = axis['observable']
    measured = []
    for rank, member in enumerate(members):
        site, rows = member['site'], member['rows']
        if member['case_id'] != spec['selection_order'][rank]:
            raise ValueError('frozen sweep order changed')
        if any(not site.get(key) or site[key] != first.get(key) for key in FIXED):
            raise ValueError('sweep fixed reviewed source changed')
        if site.get('posted_interval_m') != first.get('posted_interval_m'):
            raise ValueError('sweep fixed posted interval changed')
        if len(rows) < 3 or any(row['case_id'] != member['case_id'] or
                                row['original_frame'] != rows[0]['original_frame'] + i
                                for i, row in enumerate(rows)):
            raise ValueError('sweep original frame join changed')
        if name == 'conflict_gap_m':
            actor_id = rows[0].get('conflict_actor_id')
            if not site.get('traffic_conflict_source_sha256') or not all(
                    row.get('traffic_conflict_source_sha256') ==
                    site['traffic_conflict_source_sha256'] and
                    row.get('conflict_actor_id') == actor_id for row in rows) or not actor_id:
                raise ValueError('sweep conflict source missing')
            values = [row.get('actual_actor_body_gap_m') for row in rows]
        elif name == 'posted_offset_m':
            if not all(row.get('reviewed_posted_end_x_m') ==
                       site['posted_interval_m'][1] for row in rows):
                raise ValueError('sweep posted boundary source missing')
            values = [(row['body_west_x_m'] + row['body_east_x_m']) / 2 -
                      row['reviewed_posted_end_x_m'] for row in rows]
        else:
            raise ValueError('unknown sweep observable')
        if any(type(value) not in (int, float) for value in values):
            raise ValueError('sweep original measurement missing')
        point = spec['selection_order'][rank]
        selected = next(case for case in
                        json.loads((ROOT / 'proposals/cases.json').read_text())['cases']
                        if case['case_id'] == point)
        if selected['sweep_point'][axis['variable']] != values[0]:
            raise ValueError('diagnostic sweep setpoint and original value differ')
        measured.append({'case_id': point, 'actual_values_m': values,
                         'diagnostic_fixture_sha256': member['fixture_sha256'],
                         'requested_point': selected['sweep_point']})
    return {'sweep_id': spec['sweep_id'], 'observable': name,
            'fixed_source_keys': list(FIXED), 'members': measured,
            'diagnostic_fixture': True, 'legal_judgment': None,
            'physical_acceptance_claimed': False}


def main() -> None:
    cases = json.loads((ROOT / 'proposals/cases.json').read_text())
    report = []
    negatives = []
    for spec in cases['sweep_specs']:
        members = [load(case_id) for case_id in spec['selection_order']]
        report.append(audit(spec, members))
        altered = json.loads(json.dumps(members))
        altered[1]['site']['map_sha256'] = '0' * 64
        try:
            audit(spec, altered)
        except ValueError as error:
            if 'fixed reviewed source changed' not in str(error):
                raise
            negatives.append({'sweep_id': spec['sweep_id'],
                              'tamper': 'map_sha256', 'error': str(error)})
        else:
            raise ValueError('changed fixed source accepted')
        altered = json.loads(json.dumps(members))
        field = ('actual_actor_body_gap_m' if spec['axes'][0]['observable'] == 'conflict_gap_m'
                 else 'reviewed_posted_end_x_m')
        altered[1]['rows'][0].pop(field)
        try:
            audit(spec, altered)
        except (ValueError, KeyError) as error:
            negatives.append({'sweep_id': spec['sweep_id'],
                              'tamper': field, 'error': str(error)})
        else:
            raise ValueError('missing original sweep measurement accepted')
    (ROOT / 'cpu-sweep-comparison-proof.json').write_text(json.dumps({
        'format': 'worker-controlled-judgment-sweep-diagnostic',
        'sweeps': report, 'negative_probes': negatives,
        'legal_judgment': None, 'physical_acceptance_claimed': False},
        indent=2, sort_keys=True) + '\n')
    print('controlled sweep groups passed:', len(report),
          'negative probes:', len(negatives))


if __name__ == '__main__':
    main()
