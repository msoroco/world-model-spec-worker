"""Author explicit synthetic software diagnostics for six red-arrow cases.

The shared Native-shaped graph and video fixture checks adapter compatibility;
case-specific source text checks the measured red-arrow distinction. No output
is an original recording or evidence of physical signal operation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
ASSIGNMENT = HERE.name
BASE = ROOT / 'work/testing__C111610__NRS-484B-307-4a__motor_vehicle_driver/diagnostic-crosswalk_clear_turn.json'
PLAN = json.loads((HERE / 'case-plan.json').read_text())
ASSIGNMENT_SHA = hashlib.sha256((ROOT / 'inputs' / ASSIGNMENT / 'assignment.json').read_bytes()).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n'


def main():
    base = json.loads(BASE.read_text())
    for case in PLAN['cases']:
        suffix = case['case_suffix']
        files = dict(base['files'])
        for name in ('turn-history.jsonl', 'intersection-context.json', 'acquisition.json', 'fixture-provenance.json'):
            files.pop(name, None)
        site = {'source_kind': 'cpu_diagnostic_only', 'case_id': case['case_id'],
                'actor': PLAN['actor'], 'arrow_direction': 'left',
                'ego_head_id': 'diagnostic-ego-head', 'opposing_head_id': 'diagnostic-opposing-head',
                'pedestrian_permission_source_id': 'diagnostic-walk-context',
                'other_traffic_actor_id': 'diagnostic-traffic-actor',
                'arrow_destination_lane_id': 2, 'straight_destination_lane_id': 3}
        rows = []
        for frame in range(9):
            ped = suffix in ('yield_pedestrian', 'continue_pedestrian') and 1 <= frame <= (6 if suffix == 'continue_pedestrian' else 4)
            traffic = suffix in ('yield_other_traffic', 'continue_other_traffic') and 1 <= frame <= (6 if suffix == 'continue_other_traffic' else 4)
            rows.append({'frame': frame, 'ego_head_id': site['ego_head_id'],
                         'opposing_head_id': site['opposing_head_id'], 'ego_red': True,
                         'opposing_red': True, 'ego_arrow_direction': 'left',
                         'pedestrian_permission_source_id': site['pedestrian_permission_source_id'],
                         'pedestrian_inside_adjacent_crosswalk': ped,
                         'pedestrian_lawful_context': ped,
                         'other_traffic_actor_id': site['other_traffic_actor_id'],
                         'other_traffic_lawful_context': traffic,
                         'other_traffic_in_intersection': traffic,
                         'ego_route_lane_id': 3 if suffix == 'wrong_movement' else 2,
                         'ego_in_intersection': frame >= 6,
                         'ego_speed_mps': 0.0 if frame < 5 else 2.0})
        files['red-arrow-observations.json'] = encode(rows)
        files['source_site.json'] = encode(site)
        files['fixture-provenance.json'] = encode({
            'scope': 'CPU synthetic software diagnostic only',
            'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
            'case_specific_sources': ['red-arrow-observations.json', 'source_site.json']})
        files['acquisition.json'] = encode({name: {'kind': 'synthetic_diagnostic',
            'sha256': hashlib.sha256(files[name].encode()).hexdigest()}
            for name in ('red-arrow-observations.json', 'source_site.json')})
        spec = {'files': files, 'graphs': base['graphs'], 'videos': base['videos']}
        spec_path = HERE / ('diagnostic-' + suffix + '.json')
        spec_path.write_text(json.dumps(spec, indent=2) + '\n')
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'assignment-source.json',
                               'source': 'inputs/' + ASSIGNMENT + '/assignment.json',
                               'sha256': ASSIGNMENT_SHA}],
                  'generator': {'source': str(spec_path.relative_to(ROOT)),
                                'sha256': hashlib.sha256(spec_path.read_bytes()).hexdigest()}}
        (HERE / ('diagnostic-' + suffix + '-recipe.json')).write_text(json.dumps(recipe, indent=2) + '\n')
    print('authored', len(PLAN['cases']), 'explicit synthetic diagnostic recipes')


if __name__ == '__main__':
    main()
