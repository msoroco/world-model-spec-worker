"""Independent saved-source comparison for the paired slow-traffic cases."""
import argparse
import hashlib
import json
from pathlib import Path

from slow_traffic_saved_measure import measure_original

NAMES = ('slow-traffic-trace.jsonl', 'video_frames.jsonl',
         'slow-traffic-context.json', 'road.xodr')


def require(value, message):
    if not value:
        raise ValueError(message)


def load(folder):
    folder = Path(folder)
    raw = []
    for name in NAMES:
        path = folder / name
        require(path.is_file(), 'Missing required source: ' + name)
        raw.append(path.read_bytes())
    measured = measure_original(*raw)
    rows = [json.loads(line) for line in raw[0].splitlines()]
    return {'raw': raw, 'measurement': measured, 'rows': rows,
            'hashes': {name: hashlib.sha256(data).hexdigest()
                       for name, data in zip(NAMES, raw)}}


def compare(right, away):
    a, b = right, away
    require(a['raw'][3] == b['raw'][3], 'Comparison OpenDRIVE differs')
    ca, cb = json.loads(a['raw'][2]), json.loads(b['raw'][2])
    for key in ('assignment_id', 'native_survey', 'forward_lane_id',
                'opposing_lane_id', 'right_shoulder_lane_id',
                'right_paved_edge_y_m', 'paved_width_m'):
        require(ca.get(key) == cb.get(key), 'Comparison highway context differs: ' + key)
    ra, rb = a['rows'], b['rows']
    require(len(ra) == len(rb) == 600, 'Comparison original frame count differs')
    for index, (x, y) in enumerate(zip(ra, rb)):
        for key in ('time_s', 'video_frame', 'ego_requested_speed_mps',
                    'follower_free_flow_request_mps'):
            require(x.get(key) == y.get(key),
                    'Comparison fixed policy or time differs: ' + key + ' at ' + str(index))
        require(x['ego_id'] != x['traffic_id'] and y['ego_id'] != y['traffic_id'],
                'Comparison participant identity missing')
        require(set(x['camera_native_frames']) == set(y['camera_native_frames']),
                'Comparison camera policy differs')
    left = a['measurement']['closest_right_body_edge_to_paved_edge_m']
    center = b['measurement']['closest_right_body_edge_to_paved_edge_m']
    require(left < center, 'Requested rightward versus lane-center contrast absent')
    return {'format': 'c230259-independent-saved-comparison-v1',
            'comparison_id': 'training__C230259__NRS-484B-627-1a__motor_vehicle_driver__comparison',
            'right_source_hashes': a['hashes'], 'away_source_hashes': b['hashes'],
            'right_edge_distance_m': left, 'away_edge_distance_m': center,
            'fixed_source_checks_passed': True, 'requested_contrast_observed': True,
            'legal_extreme_right_verdict': None, 'physical_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--right-attempt', required=True)
    parser.add_argument('--away-attempt', required=True)
    args = parser.parse_args()
    print(json.dumps(compare(load(args.right_attempt), load(args.away_attempt)),
                     sort_keys=True))


if __name__ == '__main__':
    main()
