"""CPU geometry and actor-source probes for cited crosswalk alternatives.

These synthetic rows do not establish Native realization or legal applicability.
"""
import argparse
import hashlib
import json
from pathlib import Path

from opposite_half_probe import BASE, CHANGES, CANDIDATES

CASES = {
    'crosswalk_inside': 'cited_287', 'crosswalk_outside': 'cited_287',
    'guard_direction': 'cited_350', 'guard_absent': 'cited_350',
    'direction_two_way': 'directional_half', 'direction_one_way': 'directional_half',
    'service_animal_absent': 'cited_290_service_animal',
    'service_animal_present': 'cited_290_service_animal',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_rows(case):
    if case not in CASES:
        raise ValueError('Unknown branch case')
    branch = CASES[case]
    rows = []
    for frame in range(480):
        ego_y = -40 + min(frame, 240) * .16
        pedestrian_y = -7.0 if case == 'crosswalk_outside' else -11.0
        pedestrian_x = -1.75 if branch == 'directional_half' else 1.75
        guard = case == 'guard_direction'
        service = case == 'service_animal_present'
        rows.append({'native_frame': frame + 100, 'time_s': frame / 20,
                     'ego_body_xy_m': [[.8, ego_y - 2.6], [2.7, ego_y - 2.6],
                                       [2.7, ego_y + 2.6], [.8, ego_y + 2.6]],
                     'pedestrian_body_xy_m': [[pedestrian_x - .2, pedestrian_y - .2],
                                               [pedestrian_x + .2, pedestrian_y - .2],
                                               [pedestrian_x + .2, pedestrian_y + .2],
                                               [pedestrian_x - .2, pedestrian_y + .2]],
                     'marked_crosswalk_y_range_m': [-12.0, -10.0],
                     'northbound_lane': {'id': -1, 'center_x_m': 1.75, 'direction_xy': [0, 1]},
                     'other_lane': {'id': 1, 'center_x_m': -1.75,
                                    'direction_xy': [0, 1] if case == 'direction_one_way' else [0, -1]},
                     'school_guard_body_xy_m': [[3.6, -11.2], [4.0, -11.2],
                                                 [4.0, -10.8], [3.6, -10.8]] if guard else None,
                     'school_guard_stop_arm_vector_xy': [1, 0] if guard else None,
                     'school_guard_employment_verified': False,
                     'blind_person_declared': branch == 'cited_290_service_animal',
                     'service_animal_body_xy_m': [[1.4, -11.5], [1.8, -11.5],
                                                   [1.8, -11.1], [1.4, -11.1]] if service else None,
                     'service_animal_legally_verified': False})
    return {'format': 'c111256-additional-branch-source-v1', 'case': case,
            'branch': branch, 'source_kind': 'synthetic_native_sample',
            'rate_hz': 20, 'frames': rows, 'legal_verdict': None}


def measure(source, case, candidate):
    if case not in CASES or candidate not in CANDIDATES:
        raise ValueError('Unknown case or candidate')
    document = json.loads(source.read_text())
    if document.get('case') != case or document.get('branch') != CASES[case] or document.get('source_kind') != 'synthetic_native_sample':
        raise ValueError('Source case or branch differs')
    rows = document.get('frames')
    if not isinstance(rows, list) or len(rows) != 480:
        raise ValueError('Exact 480-frame source required')
    for index, row in enumerate(rows):
        if row['native_frame'] != index + 100 or abs(row['time_s'] - index / 20) > 1e-9:
            raise ValueError('Native frame join differs')
        if row['northbound_lane']['direction_xy'] != [0, 1] or row['northbound_lane']['id'] != -1:
            raise ValueError('Frozen ego route differs')
    branch = CASES[case]
    if branch == 'cited_287':
        inside = sum(all(-12 <= point[1] <= -10 for point in row['pedestrian_body_xy_m'])
                     for row in rows)
        observation = {'pedestrian_body_inside_marked_crosswalk_frames': inside,
                       'pedestrian_body_outside_marked_crosswalk_frames': 480 - inside}
    elif branch == 'cited_350':
        guard = sum(row['school_guard_body_xy_m'] is not None and
                    row['school_guard_stop_arm_vector_xy'] == [1, 0] for row in rows)
        observation = {'guard_body_and_stop_arm_observed_frames': guard,
                       'guard_employment_verified': False,
                       'highway_clear_of_all_persons_verified': False}
    elif branch == 'directional_half':
        same = sum(row['other_lane']['direction_xy'] == row['northbound_lane']['direction_xy']
                   for row in rows)
        observation = {'opposite_side_lane_same_travel_direction_frames': same,
                       'pedestrian_on_ego_directional_half_frames': same,
                       'one_way_authority_verified': False}
    else:
        animal = sum(row['service_animal_body_xy_m'] is not None for row in rows)
        observation = {'source_shaped_service_animal_body_frames': animal,
                       'blind_person_declared_frames': sum(row['blind_person_declared'] for row in rows),
                       'blindness_and_service_animal_verified': False}
    return {'format': 'c111256-additional-branch-measurement-v1', 'case': case,
            'branch': branch, 'candidate': candidate, 'source_sha256': sha(source),
            'frames_joined': 480, 'source_kind': 'synthetic_native_sample',
            'observation': observation, 'knobs': BASE | CHANGES[candidate],
            'legal_verdict': None, 'physical_acceptance_claimed': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--case', choices=CASES, required=True)
    p.add_argument('--candidate', choices=CANDIDATES, required=True)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    result = measure(a.source, a.case, a.candidate)
    if a.output.exists():
        raise ValueError('Retain prior measurement')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case': a.case, 'candidate': a.candidate,
                      'observation': result['observation'], 'legal_verdict': None}))
