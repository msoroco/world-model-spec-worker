"""Bind the exact primary Native bundle for the first selected signed-zone case."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = 'training__C179819__NRS-484B-620-2__motor_vehicle_driver'
CASE = AID + '__probe_03'


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    bundle = HERE / 'selected_primary'
    names = ('runner.py', 'config.json', 'tests/test_bundle.py')
    files = [{'path': name, 'content': (bundle / name).read_text()} for name in names]
    construction = {
        'format': 'worker-construction', 'assignment_id': AID,
        'case_id': CASE, 'cell_id': 'C179819', 'law_id': 'NRS-484B-620-2',
        'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py',
        'recording_description': json.loads((bundle / 'config.json').read_text())['recording_description'],
        'files': files,
    }
    path = HERE / 'selected-primary-construction.json'
    write(path, construction)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {'assignment_id': AID, 'cases': [{
        'case_id': CASE, 'construction': 'selected-primary-construction.json',
        'construction_sha256': digest, 'candidate_risk': {'status': 'physical',
            'reason': 'Signed-zone placement and requested-speed tracking must be checked on the surveyed local map'},
        'candidates': [],
    }]}
    write(HERE / 'selected-offline-manifest.json', manifest)
    print(json.dumps({'construction_sha256': digest, 'case_id': CASE}, sort_keys=True))


if __name__ == '__main__':
    main()
