"""Bind source-current inline construction probes for four exact night cases."""

from hashlib import sha256
import json
from pathlib import Path

from native_headlamp_probe import CASE_ID, NIGHT_CASES, check_config


HERE = Path(__file__).resolve().parent
ASSIGNMENT = CASE_ID.rsplit('__', 1)[0]
SOURCE_FILES = (
    'native_headlamp_probe.py', 'headlamp_camera.py', 'headlamp_source_capture.py',
    'headlamp_follow_route.py', 'headlamp_roadway_capture.py',
    'headlamp_follow_measurement.py', 'headlamp_finalizer.py',
    'tests/test_native_headlamp_probe.py', 'tests/test_headlamp_follow_route.py',
    'tests/test_headlamp_source_capture.py', 'tests/test_headlamp_camera.py',
    'tests/test_headlamp_roadway_capture.py', 'tests/test_headlamp_follow_measurement.py',
    'tests/test_headlamp_finalizer.py',
)


def build():
    base = json.loads((HERE / 'probe-config.json').read_text())
    cases = []
    for case_id, (gap_ft, uppermost) in NIGHT_CASES.items():
        config = {**base, 'selected_case_id': case_id,
                  'requested_gap_ft': gap_ft,
                  'requested_uppermost_distribution': uppermost}
        check_config(config)
        suffix = case_id.removeprefix(ASSIGNMENT + '__')
        config_rel = f'night-probes/{suffix}-config.json'
        construction_rel = f'night-probes/{suffix}-construction.json'
        config_bytes = (json.dumps(config, indent=2) + '\n').encode()
        (HERE / config_rel).parent.mkdir(parents=True, exist_ok=True)
        (HERE / config_rel).write_bytes(config_bytes)
        files = [{'path': 'config.json', 'content': config_bytes.decode()}]
        files.extend({'path': name, 'content': (HERE / name).read_text()}
                     for name in SOURCE_FILES)
        construction = {
            'format': 'worker-inline-construction', 'case_id': case_id,
            'cell_id': 'C178038', 'law_id': 'NRS-484D-215-2',
            'actor': 'motor_vehicle_driver', 'entrypoint': 'native_headlamp_probe.py',
            'recording_description': config['case']['recording_description'],
            'files': files,
            'measurement_plan': {'original_rows': ['following_footprints.jsonl',
                                                   'headlamp_readbacks.jsonl',
                                                   'roadway_environment.jsonl'],
                                 'saved_finalizer': 'headlamp_finalizer.py',
                                 'legal_judgment': None},
            'static_checks': ['native_headlamp_probe.py --check --config config.json'],
            'termination_rules': ['80 original 20 Hz frames or fail'],
            'mechanisms': ['CARLA connected same-lane route', 'two feedback-controlled vehicles',
                           'Native high/low beam readback', 'Native body footprints',
                           'four synchronized RGB streams', 'Native roadway and sun readback'],
        }
        construction_bytes = (json.dumps(construction, indent=2) + '\n').encode()
        (HERE / construction_rel).write_bytes(construction_bytes)
        cases.append({'case_id': case_id, 'construction': construction_rel,
                      'construction_sha256': sha256(construction_bytes).hexdigest(),
                      'physical_risk': {
                          'trigger': 'Native route or actual body-gap/beam readback may differ from request.',
                          'observable': 'Original actor bodies, light bits and four camera frame joins.',
                          'response': 'Retain attempt and require original-source review before delivery.'}})
    manifest = {'format': 'worker-construction-probe-manifest',
                'assignment_id': ASSIGNMENT, 'cases': cases}
    (HERE / 'night-probes-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    build()
