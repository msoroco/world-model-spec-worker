"""Four unselected C405647 official regulatory vehicle requests per case."""
import hashlib
import json
from pathlib import Path

from geometry import CASES, native_track_requests, requested_tracks

CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
ASSIGNMENT = 'training__C405647__NRS-484B-267-1a__motor_vehicle_driver'
LAW_SHA256 = '05acca6d9cdbea0707963bae635458009d558500a8d40a96ce4fa9d8ca5a8d86'


def _sha(data):
    return hashlib.sha256(data.encode()).hexdigest()


def _camera_plan(candidate):
    overview_x = 48 if candidate == 'fallback1' else 70
    lamp_fov = 48 if candidate == 'fallback3' else 70
    return [
        {'name': 'overview', 'attachment': 'world', 'xyz_m': [overview_x, -25, 35],
         'width': 1920, 'height': 1080, 'fov_deg': 80,
         'purpose': 'subject clearance and approach relative movement'},
        {'name': 'front_lamp', 'attachment': 'world', 'xyz_m': [18, -12, 5],
         'width': 1280, 'height': 720, 'fov_deg': lamp_fov,
         'purpose': 'front lamp visibility and flash state; qualification separately reviewed'},
        {'name': 'rear_approach', 'attachment': 'world', 'xyz_m': [-15, -14, 9],
         'width': 1280, 'height': 720, 'fov_deg': 90,
         'purpose': 'approaching vehicle identity, pose and gap'},
        {'name': 'subject_reference', 'attachment': 'subject', 'xyz_m': [1, 0, 1.5],
         'width': 1280, 'height': 720, 'fov_deg': 105,
         'purpose': 'subject forward reference and officer direction, if present'}]


def construction(case, candidate):
    if case not in CASES or candidate not in CANDIDATES:
        raise ValueError('Unknown case or candidate')
    knobs = {'approach_start_x_m': -10 if candidate == 'fallback2' else -20,
             'subject_speed_mps': 2.5 if candidate == 'fallback3' else 3,
             'lane_change_start_s': 1 if candidate == 'fallback1' else 2,
             'lane_change_duration_s': 3}
    rows = requested_tracks(case, **knobs)
    native_rows = native_track_requests(case, **knobs)
    # The policy pairs always hold the approach and requested lamp states fixed
    # across the two subject behaviors. A later Native run must prove this.
    serialized = ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows)
    native_serialized = ''.join(json.dumps(row, sort_keys=True) + '\n' for row in native_rows)
    return {
        'format': 'c405647-1a-unselected-native-request-v1',
        'case_id': ASSIGNMENT + '__' + case,
        'case_suffix': case, 'candidate_id': candidate,
        'status': 'unselected_cpu_draft', 'law_text_sha256': LAW_SHA256,
        'frozen_cell': {'layout': 'road', 'maneuver': 'travel',
                        'control': 'emergency_vehicle'},
        'actor': 'motor_vehicle_driver', 'duration_s': 24, 'rate_hz': 20,
        'requested_subject_behavior': ('clear_inner_lane_before_approach' if case == 'official_1'
                                       else 'continue_inner_lane_during_approach'),
        'knobs': knobs, 'camera_plan': _camera_plan(candidate),
        'requested_tracks_sha256': _sha(serialized),
        'native_track_requests_sha256': _sha(native_serialized),
        'requested_track_rows': len(rows),
        'source_scope_sha256': hashlib.sha256((Path(__file__).parent / (
            'statutory-scope.json' if (Path(__file__).parent / 'statutory-scope.json').is_file()
            else 'source-scope.json')).read_bytes()).hexdigest(),
        'trigger': None if candidate == 'primary' else {
            'fallback1': 'saved_subject_clearance_or_lane_drift',
            'fallback2': 'saved_approach_catchup_outside_capture_window',
            'fallback3': 'source_bound_original_front_lamp_visibility_below_capture_target'
        }[candidate],
        'trigger_is_legal_threshold': False,
        'vehicle_authority_lamp_qualification_or_immediacy_verified': False,
        'physical_success_claimed': False
    }


if __name__ == '__main__':
    import sys
    print(json.dumps(construction(sys.argv[1], sys.argv[2]), indent=2))
