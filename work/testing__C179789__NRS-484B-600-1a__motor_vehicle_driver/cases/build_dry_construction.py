"""Rebuild the exact dry/open-traffic diagnostic construction from returned sources."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASE = 'testing__C179789__NRS-484B-600-1a__motor_vehicle_driver__dry_open_traffic'
FILES = ('runner.py', 'config.json', 'camera_setup.py', 'camera_encoder.py',
         'condition_capture.py', 'condition_construction.py',
         'traffic_construction.py', 'traffic_controller.py',
         'conditions_measurements.py', 'finalizer.py', 'measurement-contract.json',
         'road_packet.json', 'surface_packet.json',
         'surface.txt', 'weather.json',
         'tests/test_cameras.py', 'tests/test_camera_encoder.py',
         'tests/test_condition_capture.py', 'tests/test_condition_construction.py',
         'tests/test_conditions.py', 'tests/test_finalizer.py', 'tests/test_runner_entry.py',
         'tests/test_traffic_controller.py')


def build():
    config = json.loads((ROOT / 'config.json').read_text())
    if config['selected_case_id'] != CASE:
        raise ValueError('Root dry case selection changed')
    package = {'case_id': CASE, 'law_id': config['law_id'],
               'cell_id': config['cell_id'], 'actor': config['actor'],
               'entrypoint': 'runner.py', 'recording_description': config['recording_description'],
               'files': [{'path': name, 'content': (ROOT / name).read_text()} for name in FILES],
               'status': 'diagnostic_draft',
               'measurement_plan': {'source': 'original Native frame, camera, surface and weather sources',
                                    'method': 'conditions_measurements.analyze; engineering surrogate only'},
               'static_checks': ['exact six-case inventory', 'four original cameras',
                                 '20 Hz and 45-second recording'],
               'termination_rules': ['complete 900 original frames or fail without sealing'],
               'mechanisms': {'ego_and_lead': 'Native actors and bounded body-gap controls',
                              'road_conditions': 'reviewed source packets with Native readback and ray probe'}}
    path = ROOT / 'construction.json'
    path.write_text(json.dumps(package, indent=2) + '\n')
    print(json.dumps({'case_id': CASE, 'construction': str(path),
                      'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}, sort_keys=True))


if __name__ == '__main__':
    build()
