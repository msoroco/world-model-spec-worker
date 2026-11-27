"""Materialize exact red-curb construction bundles from owned source files."""

from __future__ import annotations

import json
from pathlib import Path

from red_curb import CASES
from source_packet import ASSIGNMENT

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MODULES = ('runner.py', 'analysis.py', 'red_curb.py', 'source_packet.py', 'native_capture.py',
           'tests/test_red_curb.py', 'tests/test_source_packet.py',
           'tests/test_native_capture.py')
CAMERAS = (('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))


def description():
    channels = (
        ('red_curb_location', 'source geometry', 'original reviewed red paint and exact edge extent'),
        ('sign_and_vehicle_status', 'source status', 'original sign text and verified vehicle classification'),
        ('original_halt_activity', 'Native frame and seconds', 'full original stop, standing or parking interval'),
        ('exception_purpose', 'original events', 'passenger, business or U.S. mail activity and source context'),
        ('attendance_and_engine', 'original events', 'attended and motor-running status separately retained'),
        ('governing_context', 'source status', 'traffic conflict and police or device directions'),
        ('camera_frame_identity', 'Native frame', 'four original synchronized camera frame joins'),
    )
    return {'channels': [
        {'name': name, 'unit': unit, 'method': method,
         'sampling_rate_hz': 20, 'time_window': 'complete original 1806-second capture',
         'reference_frame': 'reviewed municipal curb and original Native frame',
         'uncertainty': 'CPU fixtures cannot establish actual markings, people or pixels'}
        for name, unit, method in channels],
        'context_inputs': [
            {'name': 'reviewed_municipal_red_curb', 'unit': 'source hashes',
             'method': 'jurisdiction, painted edge, signs and governing context'},
            {'name': 'reviewed_vehicle_and_activity', 'unit': 'source hashes',
             'method': 'vehicle status, passenger, business or mail activity'}],
        'limitations': [
            'Necessary business period and expeditious mail deposit remain legal judgments.',
            'Actual markings, participation and complete camera pixels require local review.']}


def write():
    desc = description()
    paths = []
    for index, case in enumerate(CASES):
        cid = ASSIGNMENT + '__' + case.name
        for candidate in ('primary', 'fallback1'):
            folder = ROOT if index == 0 and candidate == 'primary' else ROOT / 'cases' / case.name
            folder.mkdir(parents=True, exist_ok=True)
            config = {'assignment_id': ASSIGNMENT, 'law_id': 'LVMC-11-52-030-A',
                      'cell_id': 'C229452', 'actor': 'motor_vehicle_driver',
                      'selected_case_id': cid,
                      'supported_case_ids': [ASSIGNMENT + '__' + item.name for item in CASES],
                      'rate_hz': 20, 'duration_s': 1806, 'frame_count': 36120,
                      'required_atoms': [], 'source_packets': [],
                      'candidate_id': candidate,
                      'cameras': [{'name': name, 'width': width, 'height': height,
                                   'pose_strategy': 'reviewed original red curb, sign, vehicle and activity',
                                   'fov_deg': 90} for name, width, height in CAMERAS],
                      'case': {'case_id': cid, 'recording_description': desc}}
            config_path = folder / ('config.json' if candidate == 'primary'
                                    else 'fallback1-config.json')
            config_path.write_text(json.dumps(config, indent=2) + '\n')
            files = [{'path': name, 'source': str((ROOT / name).relative_to(REPO)),
                      'content': (ROOT / name).read_text(encoding='utf-8')}
                     for name in MODULES]
            files.append({'path': 'config.json', 'content': config_path.read_text()})
            construction = {'law_id': 'LVMC-11-52-030-A', 'cell_id': 'C229452',
                            'actor': 'motor_vehicle_driver', 'case_id': cid,
                            'candidate_id': candidate, 'entrypoint': 'runner.py',
                            'diagnostic_only': True,
                            'recording_description': desc, 'files': files,
                            'measurement_plan': 'original complete halt interval and reviewed curb, sign and exception sources',
                            'static_checks': ['municipal and red-painted edge source hashes',
                                              'vehicle subtype and sign authority hashes',
                                              'Native actor and four-camera readback'],
                            'termination_rules': ['36120 synchronized Native ticks',
                                                  'encoders closed and world restoration verified'],
                            'mechanisms': ['source-gated physical red-curb halt',
                                           'complete original activity and four-camera capture']}
            construction_path = folder / ('construction.json' if candidate == 'primary'
                                          else 'fallback1-construction.json')
            construction_path.write_text(json.dumps(construction, indent=2) + '\n')
            paths.append((cid, candidate, construction_path))
    return paths


if __name__ == '__main__':
    for cid, candidate, path in write():
        print(cid, candidate, path.stat().st_size)
