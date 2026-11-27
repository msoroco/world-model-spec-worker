"""Build exact 600-frame four-camera requests for the green-arrow cases."""

import json
import os
from pathlib import Path

from controller import SUFFIXES

ROOT = Path(__file__).resolve().parent.parent
AID = 'training__C111603__NRS-484B-307-4a__motor_vehicle_driver'
CAMERAS = (('overview', 1920, 1080, 85),
           ('approach', 1280, 720, 90),
           ('reference_corner', 1280, 720, 85),
           ('driver_reference', 1280, 720, 90))


def build(suffix):
    if suffix not in SUFFIXES:
        raise ValueError('Unknown exact selected case')
    case_id = AID + '__' + suffix
    channels = [
        ('signal_native_and_pixels', 'Original signal actor ID, raw state and four-camera pixel reference'),
        ('participant_native_and_video', 'Original ego, pedestrian, other-traffic poses and camera frame map'),
        ('dev.traffic_signal', 'Raw signal state and independent original arrow-only pixel review'),
        ('dev.governs', 'Original Native head identity, approach geometry and facing pixel review'),
        ('drv.turning', 'Original ego route, body and heading during turn'),
        ('kin.heading', 'Original ego transform heading by Native frame'),
        ('drv.entering_intersection', 'Original ego body and surveyed intersection bounds'),
        ('ru.pedestrian', 'Original pedestrian body, trajectory and independent permission review'),
        ('st.crosswalk', 'Original adjacent crosswalk survey and participant body'),
        ('drv.in_intersection', 'Original other-traffic body and independent permission review'),
        ('drv.yields_to', 'Original ego and participant motion timing; causation review pending'),
    ]
    description = {'channels': [
        {'name': name, 'method': method, 'sampling_rate_hz': 20,
         'time_window': '600 frames', 'unit': 'structured',
         'reference_frame': 'original Native frame joined to four-camera map',
         'uncertainty': 'Signal governance, participant lawfulness and yielding require independent original review'}
        for name, method in channels],
        'context_inputs': [],
        'limitations': [
            'Generic Native Green state does not establish a green turn arrow alone',
            'Requested motion and overlap do not establish legal right-of-way or yielding',
        ]}
    return {
        'format': 'c111603-exact-native-request-v1',
        'assignment_id': AID, 'case_id': case_id, 'selected_case_id': case_id,
        'supported_case_ids': [AID + '__' + name for name in SUFFIXES],
        'law_id': 'NRS-484B-307-4a', 'cell_id': 'C111603',
        'actor': 'motor_vehicle_driver', 'frames': 600, 'rate_hz': 20,
        'duration_s': 30, 'camera_sources': [c[0] for c in CAMERAS],
        'cameras': [
            {'name': name, 'width': width, 'height': height, 'fov_deg': fov,
             'pose_strategy': 'source surveyed fixed world' if name in ('overview', 'reference_corner') else 'ego mounted'}
            for name, width, height, fov in CAMERAS],
        'required_atoms': [], 'source_packets': [],
        'source_scope': 'original Native intersection, signal and participants pending',
        'status': 'authored_cpu_request_original_native_pending',
        'case': {'case_id': case_id, 'recording_description': description},
        'recording_description': description,
        'requested_route': 'contrary_turn' if suffix == 'direction_contrary' else 'indicated_turn',
        'requested_control_mode': suffix,
    }


def main():
    scratch = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
    scratch.mkdir(parents=True, exist_ok=True)
    config = build('direction_indicated')
    for path in (ROOT / 'native' / 'config.json', ROOT / 'config.json'):
        stage = scratch / ('c111603-' + path.parent.name + '-config.stage')
        stage.write_text(json.dumps(config, indent=2) + '\n')
        os.replace(stage, path)
    print(json.dumps({'selected_case_id': config['case_id'],
                      'supported_cases': len(config['supported_case_ids'])}))


if __name__ == '__main__':
    main()
