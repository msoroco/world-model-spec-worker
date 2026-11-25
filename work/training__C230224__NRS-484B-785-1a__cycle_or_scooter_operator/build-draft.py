"""Bind exact selected scooter path case to CPU-checkable Native source."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
CASES = ('controlled_1', 'controlled_at_cap', 'controlled_2')


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def main():
    manifest = {'assignment_id': AID, 'cases': []}
    for suffix in CASES:
        case = AID + '__' + suffix
        source = HERE / ('native' if suffix == 'controlled_1' else f'cases/{suffix}/native')
        cfg = json.loads((source/'config.json').read_text())
        names = ('runner.py', 'config.json', 'tests/test_native.py')
        files = [{'path': name, 'content': (source/name).read_text()} for name in names]
        files.append({'path': 'measure_scooter.py', 'content': (HERE/'measure_scooter.py').read_text()})
        construction = {'format': 'worker-construction', 'assignment_id': AID,
                        'case_id': case, 'cell_id': 'C230224', 'law_id': 'NRS-484B-785-1a',
                        'actor': 'cycle_or_scooter_operator', 'entrypoint': 'runner.py',
                        'recording_description': cfg['recording_description'],
                        'measurement_plan': {'entrypoint': 'measure_scooter.py',
                            'source_files': ['video_frames.jsonl', 'native_rider_trace.jsonl', 'scooter_context.json'],
                            'legal_result': None}, 'files': files}
        path = HERE/('selected-primary-construction.json' if suffix == 'controlled_1' else f'cases/{suffix}/selected-primary-construction.json')
        write(path, construction)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest['cases'].append({'case_id': case, 'construction': str(path.relative_to(HERE)),
            'construction_sha256': digest, 'candidate_risk': {'status': 'physical',
            'reason': 'Requires reviewed genuine electric scooter asset, original Native path occupancy, and applicable ordinance source'},
            'candidates': []})
    write(HERE/'selected-offline-manifest.json', manifest)
    print(json.dumps({'cases': [case['case_id'] for case in manifest['cases']]}, sort_keys=True))


if __name__ == '__main__':
    main()
