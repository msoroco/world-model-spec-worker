"""Bind exact selected scooter path case to CPU-checkable Native source."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
CASE = AID + '__controlled_1'


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def main():
    cfg = json.loads((HERE/'native/config.json').read_text())
    names = ('runner.py', 'config.json', 'tests/test_native.py')
    files = [{'path': name, 'content': (HERE/'native'/name).read_text()} for name in names]
    files.append({'path': 'measure_scooter.py', 'content': (HERE/'measure_scooter.py').read_text()})
    construction = {'format': 'worker-construction', 'assignment_id': AID,
                    'case_id': CASE, 'cell_id': 'C230224', 'law_id': 'NRS-484B-785-1a',
                    'actor': 'cycle_or_scooter_operator', 'entrypoint': 'runner.py',
                    'recording_description': cfg['recording_description'],
                    'measurement_plan': {'entrypoint': 'measure_scooter.py',
                        'source_files': ['video_frames.jsonl', 'native_rider_trace.jsonl', 'scooter_context.json'],
                        'legal_result': None}, 'files': files}
    path = HERE/'selected-primary-construction.json'
    write(path, construction)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {'assignment_id': AID, 'cases': [{'case_id': CASE,
        'construction': 'selected-primary-construction.json',
        'construction_sha256': digest, 'candidate_risk': {'status': 'physical',
        'reason': 'Requires reviewed genuine electric scooter asset, original Native path occupancy, and applicable ordinance source'},
        'candidates': []}]}
    write(HERE/'selected-offline-manifest.json', manifest)
    print(json.dumps({'construction_sha256': digest, 'case_id': CASE}, sort_keys=True))


if __name__ == '__main__':
    main()
