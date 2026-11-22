"""Independent saved-source comparison for the adjacent-crosswalk pair."""
import argparse
import json
from pathlib import Path

from analysis import measure

ROOT = Path(__file__).resolve().parent
OCCUPIED_SCENE = ROOT / 'cases/crosswalk_occupied_yield/scene.json'
FIXED = ('map_source', 'adjacent_crosswalk_source', 'ego_route_source',
         'facing_head_source', 'lawful_presence_method', 'facing_head_id',
         'adjacent_crosswalk_bounds_m', 'route_waypoints', 'crosswalk_vertices_m',
         'camera_profile', 'duration_s')


def audit(clear_attempt, occupied_attempt):
    clear_attempt, occupied_attempt = Path(clear_attempt), Path(occupied_attempt)
    if clear_attempt.resolve() == occupied_attempt.resolve():
        raise ValueError('comparison requires two distinct exact-case attempts')
    clear = measure(clear_attempt, 'crosswalk_clear_turn')
    occupied = measure(occupied_attempt, 'crosswalk_occupied_yield', OCCUPIED_SCENE)
    contexts = [json.loads((path / 'intersection-context.json').read_text())
                for path in (clear_attempt, occupied_attempt)]
    for key in FIXED:
        if not contexts[0].get(key) or contexts[0][key] != contexts[1].get(key):
            raise ValueError('paired fixed condition missing or changed: ' + key)
    if clear['lawful_occupancy_frames'] or not occupied['lawful_occupancy_frames']:
        raise ValueError('declared pedestrian occupancy variable absent')
    return {'format': 'worker-crosswalk-comparison-audit',
            'comparison_id': 'adjacent_crosswalk_lawful_occupancy',
            'status': 'passed',
            'fixed_conditions': {key: contexts[0][key] for key in FIXED},
            'deliberate_difference': 'lawful adjacent-crosswalk pedestrian occupancy',
            'clear_measurement_sources': clear['sources'],
            'occupied_measurement_sources': occupied['sources'],
            'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--clear-attempt', required=True)
    parser.add_argument('--occupied-attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.clear_attempt, args.occupied_attempt)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
