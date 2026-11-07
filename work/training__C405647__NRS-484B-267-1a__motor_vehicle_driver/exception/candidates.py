"""Unselected Native capture plans for the officer-direction branch."""
import hashlib
import json
from build import ASSIGNMENT, CASES, CANDIDATES, knobs_for, native_requests, requests


def _sha(rows):
    return hashlib.sha256(''.join(json.dumps(r, sort_keys=True) + '\n'
                           for r in rows).encode()).hexdigest()


def construction(case, candidate):
    if case not in CASES or candidate not in CANDIDATES:
        raise ValueError('Unknown case or candidate')
    knobs = knobs_for(candidate)
    return {
        'format': 'c405647-officer-direction-native-plan-v1',
        'case_id': ASSIGNMENT + '__' + case,
        'case_suffix': case, 'candidate_id': candidate,
        'status': 'unselected_native_proposal', 'knobs': knobs,
        'frozen_cell': {'layout': 'road', 'maneuver': 'travel',
                        'control': 'emergency_vehicle'},
        'actor': 'motor_vehicle_driver', 'duration_s': 24, 'rate_hz': 20,
        'requested_tracks_sha256': _sha(requests(case, candidate)),
        'native_track_requests_sha256': _sha(native_requests(case, candidate)),
        'camera_plan': [
            {'name': 'overview', 'attachment': 'world',
             'xyz_m': [70, -25, 35], 'width': 1920, 'height': 1080,
             'fov_deg': 80, 'purpose': 'approach and subject body'},
            {'name': 'front_lamp', 'attachment': 'world',
             'xyz_m': [18, -12, 5], 'width': 1280, 'height': 720,
             'fov_deg': 70, 'purpose': 'original lamp pixels; qualification separate'},
            {'name': 'rear_approach', 'attachment': 'world',
             'xyz_m': [-15, -14, 9], 'width': 1280, 'height': 720,
             'fov_deg': 90, 'purpose': 'approach identity and pose'},
            {'name': 'subject_reference', 'attachment': 'subject',
             'xyz_m': [1, 0, 1.5], 'width': 1280, 'height': 720,
             'fov_deg': 105, 'purpose': 'subject view of proposed officer'},
            {'name': 'officer_reference', 'attachment': 'world',
             'xyz_m': [knobs['officer_position_x_m'] + 4, -8.75, 3.2],
             'width': 1280, 'height': 720,
             'fov_deg': knobs['officer_camera_fov_deg'],
             'purpose': 'original officer pixels; gesture and communication unverified'}],
        'officer_actor_visual_stand_in_only': True,
        'actual_direction_content_recipient_or_identity_observed': False,
        'legal_exception_verified': False,
    }
