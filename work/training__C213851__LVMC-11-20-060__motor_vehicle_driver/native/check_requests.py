"""Check exact requested motion and isolation; no legal outcome is inferred."""

import json
import math
from pathlib import Path

from build_requests import AID, POLICIES, ROOT, sha


def read(policy, root=ROOT):
    folder = Path(root) / 'native' / policy
    config = json.loads((folder / 'config.json').read_text())
    tracks_path = folder / 'requested-tracks.jsonl'
    tracks = [json.loads(line) for line in tracks_path.read_text().splitlines()]
    if (config.get('case_id') != AID + '__' + policy or
            config.get('controller_policy') != policy or
            config.get('route') != 'road_to_private_driveway' or
            config.get('duration_s') != 30 or
            config.get('rate_hz') != 20 or
            config.get('sidewalk_route_s_interval_m') != [0, 2] or
            sha(tracks_path) != config.get('requested_tracks_sha256') or
            len(tracks) != 600):
        raise ValueError('Exact sidewalk controller request differs')
    for index, row in enumerate(tracks):
        if (row.get('frame_index') != index or
                type(row.get('time_s')) not in (int, float) or
                not math.isfinite(row['time_s']) or
                abs(row['time_s'] - (index + 1) / 20) > .001 or
                row.get('controller_policy') != policy or
                type(row.get('requested_route_s_m')) not in (int, float) or
                type(row.get('requested_speed_mps')) not in (int, float) or
                row.get('requested_roadway_traffic_policy') !=
                'fixed_context_observation'):
            raise ValueError('Exact sidewalk 20 Hz request differs')
    return config, tracks


def check_pair(root=ROOT):
    left, a = read(POLICIES[0], root)
    right, b = read(POLICIES[1], root)
    fixed_config = ('law_id', 'cell_id', 'actor', 'route', 'duration_s',
                    'rate_hz', 'sidewalk_route_s_interval_m',
                    'source_review_required')
    if any(left[key] != right[key] for key in fixed_config):
        raise ValueError('Paired sidewalk construction context differs')
    fixed_rows = ('frame_index', 'time_s',
                  'requested_pedestrian_route_s_m',
                  'requested_pedestrian_cross_track_m',
                  'requested_roadway_traffic_policy')
    if any(x[key] != y[key] for x, y in zip(a, b) for key in fixed_rows):
        raise ValueError('Paired sidewalk pedestrian or timing context differs')
    if (not any(row['requested_speed_mps'] == 0 and
                row['requested_route_s_m'] < -1.2 for row in a) or
            any(row['requested_speed_mps'] == 0 for row in b) or
            a[-1]['requested_route_s_m'] <= 2 or
            b[-1]['requested_route_s_m'] <= 2):
        raise ValueError('Paired sidewalk stop-policy targets missing')
    return {'format': 'road-to-driveway-request-check', 'passed': True,
            'case_ids': [left['case_id'], right['case_id']],
            'fixed_controller_context': list(fixed_config) + list(fixed_rows),
            'deliberate_difference': 'controller_policy',
            'actual_native_motion_observed': False,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    print(json.dumps(check_pair()))
