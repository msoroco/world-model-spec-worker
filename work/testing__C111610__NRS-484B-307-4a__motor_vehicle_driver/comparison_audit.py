"""Independent saved-source comparison for the adjacent-crosswalk pair."""
import argparse
import json
from pathlib import Path

from analysis import measure

ROOT = Path(__file__).resolve().parent
FIXED = ('map_source', 'adjacent_crosswalk_source', 'ego_route_source',
         'facing_head_source', 'lawful_presence_method', 'facing_head_id',
         'adjacent_crosswalk_bounds_m', 'route_waypoints', 'crosswalk_vertices_m',
         'camera_profile', 'duration_s')


def audit(clear_attempt, occupied_attempt):
    clear_attempt, occupied_attempt = Path(clear_attempt), Path(occupied_attempt)
    if clear_attempt.resolve() == occupied_attempt.resolve():
        raise ValueError('comparison requires two distinct exact-case attempts')
    clear = measure(clear_attempt, 'crosswalk_clear_turn', clear_attempt / 'scene.json')
    occupied = measure(occupied_attempt, 'crosswalk_occupied_yield',
                       occupied_attempt / 'scene.json')
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


def audit_traffic(clear_attempt, traffic_attempt):
    clear_attempt, traffic_attempt = Path(clear_attempt), Path(traffic_attempt)
    if clear_attempt.resolve() == traffic_attempt.resolve():
        raise ValueError('comparison requires two distinct exact-case attempts')
    clear = measure(clear_attempt, 'crosswalk_clear_turn', clear_attempt / 'scene.json')
    traffic = measure(traffic_attempt, 'lawful_traffic_yield',
                      traffic_attempt / 'scene.json')
    contexts = [json.loads((path / 'intersection-context.json').read_text())
                for path in (clear_attempt, traffic_attempt)]
    for key in FIXED:
        if not contexts[0].get(key) or contexts[0][key] != contexts[1].get(key):
            raise ValueError('paired fixed condition missing or changed: ' + key)
    if (clear['traffic_frames'] or not traffic['traffic_frames'] or
            clear['lawful_occupancy_frames'] or traffic['lawful_occupancy_frames']):
        raise ValueError('declared lawful-traffic presence variable absent')
    return {'format': 'worker-traffic-comparison-audit',
            'comparison_id': 'other_lawful_traffic_presence', 'status': 'passed',
            'fixed_conditions': {key: contexts[0][key] for key in FIXED},
            'deliberate_difference': 'original-green-entered lawful other-vehicle occupancy',
            'clear_measurement_sources': clear['sources'],
            'traffic_measurement_sources': traffic['sources'],
            'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--clear-attempt', required=True)
    parser.add_argument('--occupied-attempt')
    parser.add_argument('--traffic-attempt')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if bool(args.traffic_attempt) == bool(args.occupied_attempt):
        parser.error('select exactly one occupied or traffic attempt')
    result = (audit_traffic(args.clear_attempt, args.traffic_attempt)
              if args.traffic_attempt else audit(args.clear_attempt, args.occupied_attempt))
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
