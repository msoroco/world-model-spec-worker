"""Author two exact 20 Hz controller requests for the frozen road-exit pair."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
AID = (json.loads((ROOT / 'assignment-id.json').read_text())['assignment_id']
       if (ROOT / 'assignment-id.json').is_file() else ROOT.name)
POLICIES = ('stop_before_sidewalk', 'cross_without_stop')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def build(policy):
    if policy not in POLICIES:
        raise ValueError('Unknown exact sidewalk policy')
    case = AID + '__' + policy
    folder = ROOT / 'native' / policy
    folder.mkdir(parents=True, exist_ok=True)
    controls = []
    for index in range(600):
        if policy == 'stop_before_sidewalk':
            route_s = -8 + min(index, 180) * .035
            if index > 250:
                route_s += (index - 250) * .04
            target_speed = 0.0 if 180 <= index <= 250 else .8
        else:
            route_s = -8 + index * .04
            target_speed = .8
        controls.append({
            'frame_index': index,
            'time_s': (index + 1) / 20,
            'requested_route_s_m': round(route_s, 6),
            'requested_speed_mps': target_speed,
            'requested_pedestrian_route_s_m': round(8 - index * .025, 6),
            'requested_pedestrian_cross_track_m': 1.0,
            'requested_roadway_traffic_policy': 'fixed_context_observation',
            'controller_policy': policy,
        })
    tracks = folder / 'requested-tracks.jsonl'
    tracks.write_text(''.join(json.dumps(row, sort_keys=True) + '\n'
                              for row in controls))
    config = {
        'case_id': case,
        'law_id': 'LVMC-11-20-060',
        'cell_id': 'C213851',
        'actor': 'motor_vehicle_driver',
        'route': 'road_to_private_driveway',
        'controller_policy': policy,
        'duration_s': 30,
        'rate_hz': 20,
        'requested_tracks_sha256': sha(tracks),
        'sidewalk_route_s_interval_m': [0, 2],
        'source_review_required': ['private_driveway_connection',
                                   'sidewalk_polygon',
                                   'residence_district',
                                   'pedestrian_route'],
        'original_physical_completion_claimed': False,
        'legal_verdict_claimed': False,
    }
    write_json(folder / 'config.json', config)
    return {'case_id': case, 'tracks_sha256': sha(tracks),
            'config_sha256': sha(folder / 'config.json')}


if __name__ == '__main__':
    print(json.dumps([build(policy) for policy in POLICIES]))
