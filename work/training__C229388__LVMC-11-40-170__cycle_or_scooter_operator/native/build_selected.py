"""Bind the first source-reviewed rack placement case to an inline Native bundle."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = 'training__C229388__LVMC-11-40-170__cycle_or_scooter_operator'
CASE = AID + '__probe_01'


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    bundle = HERE/'selected_primary'
    names = ('runner.py', 'config.json', 'tests/test_bundle.py')
    files = [{'path': name, 'content': (bundle/name).read_text()} for name in names]
    construction = {'format': 'worker-construction', 'assignment_id': AID,
                    'case_id': CASE, 'cell_id': 'C229388', 'law_id': 'LVMC-11-40-170',
                    'actor': 'cycle_or_scooter_operator', 'entrypoint': 'runner.py',
                    'recording_description': json.loads((bundle/'config.json').read_text())['recording_description'],
                    'files': files}
    path = HERE/'selected-primary-construction.json'
    write(path, construction)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {'assignment_id': AID, 'cases': [{
        'case_id': CASE, 'construction': 'selected-primary-construction.json',
        'construction_sha256': digest,
        'candidate_risk': {'status': 'physical',
                           'reason': 'The reviewed rack, cycle or scooter blueprint, and pedestrian corridor may not physically exist together on the local CARLA map'},
        'candidates': []}]}
    write(HERE/'selected-offline-manifest.json', manifest)
    print(json.dumps({'construction_sha256': digest, 'case_id': CASE}, sort_keys=True))


if __name__ == '__main__':
    main()
