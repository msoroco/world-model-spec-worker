"""Independent source-bound CPU diagnostic for school-zone traversal completion."""
import argparse
import json
import math
from pathlib import Path


def evaluate(fixture, kind):
    fixture = Path(fixture)
    context = json.loads((fixture / 'school_zone_context.json').read_text())
    frames = [json.loads(line) for line in (fixture / 'video_frames.jsonl').read_text().splitlines()]
    motion_path = fixture / 'native_motion.jsonl'
    motion = [json.loads(line) for line in motion_path.read_text().splitlines()] if motion_path.exists() else []
    sources = ['school_zone_context.json', 'video_frames.jsonl', 'native_motion.jsonl']
    if len(frames) != 600 or len(motion) != 600:
        status = 'unverified' if not motion else 'not_met'
        reason = 'missing motion source' if not motion else 'truncated source motion before zone exit'
    else:
        axis = context['road_axis_xy']
        low, high = context['zone_station_bounds_m']
        stations = []
        for i, (frame, sample) in enumerate(zip(frames, motion)):
            if (frame['video_frame'] != i or sample['video_frame'] != i or
                    frame['native_frame'] != sample['native_frame'] or
                    sample['road_id'] != context['road_id'] or
                    sample['travel_direction_id'] != context['travel_direction_id'] or
                    sample['ego_actor_id'] != context['ego_actor_id']):
                raise ValueError('Physical proof source identity mismatch')
            station = sample['ego_x_m'] * axis[0] + sample['ego_y_m'] * axis[1]
            if not math.isfinite(station):
                raise ValueError('Nonfinite source position')
            stations.append(station)
        status = 'met' if stations[0] < low and stations[-1] > high and all(
            after >= before - .01 for before, after in zip(stations, stations[1:])) else 'not_met'
        reason = 'source vehicle traversed surveyed interval in 600 joined frames' if status == 'met' else 'source vehicle did not traverse full interval'
    return {
        'case_id': context['case_id'],
        'maneuver_completed': status == 'met',
        'physical_checks': {'maneuver': {
            'status': status, 'method': 'joined saved motion projected onto reviewed zone axis',
            'sources': sources, 'reason': reason}},
        'realized_observables': {'zone_traversal': {'status': status, 'source': sources}} if status == 'met' else {},
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
        'physical_acceptance_claimed': False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixture', required=True)
    parser.add_argument('--kind', choices=('complete_motion', 'incomplete_motion', 'missing_evidence'), required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = evaluate(args.fixture, args.kind)
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[args.kind]
    if result['physical_checks']['maneuver']['status'] != expected:
        raise ValueError('Source outcome differs from expected diagnostic fixture')
    Path(args.output).write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(result['case_id'], args.kind, result['physical_checks']['maneuver']['status'])


if __name__ == '__main__':
    main()
