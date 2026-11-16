"""CPU outcome fixtures for the hypothetical original-motion result branch.

These constructed positions contain no velocity. The native provenance value is
an output of the finalizer branch under test, not a claim about a CARLA capture.
"""
import argparse
import hashlib
import json
from pathlib import Path

from audit_physical_motion import geometry
from finalize_selected import motion_fields
from measure_raw import VIEWS


def body(x, y):
    return [[x - 1, y - .5, 0], [x + 1, y - .5, 0],
            [x + 1, y + .5, 0], [x - 1, y + .5, 0]]


def fixture(kind):
    rows = []; frames = []
    if kind == 'missing_evidence':
        return rows, frames
    end = 40 if kind == 'complete_motion' else 10
    for index in range(240):
        ego_x = end * index / 239
        rows.append({'frame': index, 'native_frame': index,
                     'ego': {'actor_id': 1, 'center_native_xyz_m': [ego_x, -3, 0],
                             'body_native_xyz_m': body(ego_x, -3)},
                     'lead': {'actor_id': 2, 'center_native_xyz_m': [20, 0, 0],
                              'body_native_xyz_m': body(20, 0)}})
        frames.append({'video_frame': index, 'native_frame': index,
                       'views': list(VIEWS)})
    return rows, frames


def digest_rows(rows):
    payload = ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows)
    return hashlib.sha256(payload.encode()).hexdigest()


def prove(case, kind):
    assert kind in {'complete_motion', 'incomplete_motion', 'missing_evidence'}
    rows, frames = fixture(kind)
    if kind == 'missing_evidence':
        feature = None
        status = 'unverified'
        sources = {'cpu_mock_case_definition': hashlib.sha256(case.encode()).hexdigest()}
    else:
        feature = geometry(rows, frames)
        status = 'met' if feature['complete_motion_observed'] else 'not_met'
        assert status == ('met' if kind == 'complete_motion' else 'not_met')
        sources = {'cpu_mock_actor_positions': digest_rows(rows),
                   'cpu_mock_frame_join': digest_rows(frames)}
    review = {'source_kind': 'original_native', 'status': status,
              'maneuver_completed': status == 'met',
              'method': 'hypothetical original-motion branch over CPU positions',
              'sources': sources,
              'missing_evidence': ['original Native capture'] if feature is None else []}
    mapped = motion_fields('original_native', review, sources)
    return {'format': 'c146314-physical-outcome-cpu-fixture-v1',
            'case_id': case, 'fixture_kind': kind, 'unit_mock': True,
            'original_carla_executed': False, 'original_native_observed': False,
            'speed_values_supplied': False, 'physical_acceptance_claimed': False,
            'legal_safety_verdict': None,
            'provenance_kind': mapped['provenance_kind'],
            'maneuver_completed': mapped['maneuver_completed'],
            'physical_checks': {'maneuver': mapped['check']},
            'realized_observables': {'cpu_mock_geometry': feature} if feature else {},
            'hypothetical_branch_input': review}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True,
                        choices=['complete_motion', 'incomplete_motion', 'missing_evidence'])
    args = parser.parse_args()
    assert args.case in {Path(__file__).resolve().parents[1].name + '__' + name
                         for name in ('reference', 'contrast')}
    print(json.dumps(prove(args.case, args.kind), sort_keys=True))
