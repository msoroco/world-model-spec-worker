"""Build source-shaped requests for a driveway-to-roadway return comparison.

The existing road-exit pair stays intact. These requests are a prospective
second phase in the same authored residence-district site, not observations.
"""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
AID = (json.loads((ROOT / 'assignment-id.json').read_text())['assignment_id']
       if (ROOT / 'assignment-id.json').is_file() else ROOT.name)
POLICIES = ('yield_to_approaching', 'enter_without_yield')
FRAMES = 1200


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def target(index, policy):
    """Three route phases: exit road, dwell in driveway, return to road.

    The roadway vehicle travels west toward the same road crossing. The
    alternate policy changes only the ego's pre-entry dwell, never its speed
    or the roadway vehicle's requested trajectory.
    """
    if index < 400:
        # Road approach then driveway traversal through the sidewalk.
        fraction = index / 399
        x, y = -6.25 + 6.25 * min(1.0, fraction * 1.35), -1.75
        if fraction > .74:
            x, y = 0.0, -1.75 - 7.25 * ((fraction - .74) / .26)
        speed = .8
        phase = 'road_exit'
    elif index < 560:
        x, y, speed, phase = 0.0, -9.0, 0.0, 'private_driveway_dwell'
    else:
        t = index - 560
        wait = 160 if policy == POLICIES[0] else 0
        moving = max(0, t - wait)
        # Return north across the sidewalk, then turn east onto roadway.
        if moving < 320:
            x, y = 0.0, -9.0 + min(moving / 319, 1.0) * 7.25
        else:
            x, y = min((moving - 320) * .04, 8.0), -1.75
        speed = 0.0 if t < wait else .8
        phase = 'roadway_entry'
    # A vehicle approaches from the east on the roadway in both cases.
    traffic_x = 40.1 - index * .05
    return {
        'frame_index': index,
        'time_s': round((index + 1) / 20, 6),
        'phase': phase,
        'requested_ego_world_xy_m': [round(x, 6), round(y, 6)],
        'requested_ego_speed_mps': speed,
        'requested_approaching_world_xy_m': [round(traffic_x, 6), -1.75],
        'requested_approaching_speed_mps': 1.0,
        'requested_pedestrian_world_xy_m': [round(8 - index * .0125, 6), -4.5],
        'controller_policy': policy,
    }


def build(policy):
    if policy not in POLICIES:
        raise ValueError('Unknown roadway-entry policy')
    folder = ROOT / 'native' / 'entry_return' / policy
    folder.mkdir(parents=True, exist_ok=True)
    rows = [target(index, policy) for index in range(FRAMES)]
    track = folder / 'requested-tracks.jsonl'
    track.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    config = {
        'case_id': AID + '__' + policy,
        'law_id': 'LVMC-11-20-060',
        'cell_id': 'C213851',
        'actor': 'motor_vehicle_driver',
        'site_road_sha256': sha(ROOT / 'native' / 'road' / 'road.xodr'),
        'route': 'road_exit_then_private_driveway_to_roadway',
        'controller_policy': policy,
        'duration_s': 60,
        'rate_hz': 20,
        'roadway_entry_reference_y_m': -3.5,
        'roadway_lane_y_m': -1.75,
        'sidewalk_world_y_interval_m': [-5.5, -3.5],
        'requested_tracks_sha256': sha(track),
        'source_review_required': [
            'residence_district', 'private_driveway_connection',
            'sidewalk_polygon', 'pedestrian_route',
            'approaching_vehicle_roadway_lane',
        ],
        'physical_or_legal_outcome_claimed': False,
    }
    write_json(folder / 'config.json', config)
    return {'case_id': config['case_id'], 'config_sha256': sha(folder / 'config.json'),
            'requested_tracks_sha256': sha(track)}


if __name__ == '__main__':
    print(json.dumps([build(policy) for policy in POLICIES]))
