"""Package exact C200542 source and authored Native CPU drafts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ASSIGNMENT = ROOT.name
CAMERAS = ['overview', 'approach', 'aisle_side', 'parking_bay']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    entries = []
    for suffix in ('controlled_1', 'controlled_2'):
        case_id = ASSIGNMENT + '__' + suffix
        config = {'case_id': case_id, 'case_suffix': suffix, 'cell_id': 'C200542',
                  'law_id': 'LVMC-11-52-136', 'actor': 'motor_vehicle_driver',
                  'duration_s': 30, 'rate_hz': 20, 'cameras': CAMERAS,
                  'target': 'park outside aisle' if suffix == 'controlled_1' else 'park inside aisle'}
        files = [{'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'}]
        for name in ('layout.py', 'runner.py', 'measure_aisle.py', 'tests/test_native.py'):
            files.append({'path': name, 'content': (HERE / name).read_text()})
        for name in ('assignment.json', 'witnesses.json'):
            source = Path('inputs') / ASSIGNMENT / name
            files.append({'path': name, 'content': source.read_text()})
        proposal = {'case_id': case_id, 'cell_id': 'C200542', 'law_id': 'LVMC-11-52-136',
                    'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py', 'files': files,
                    'recording_description': {'rate_hz': 20, 'duration_s': 30,
                        'cameras_required': CAMERAS,
                        'required_original_sources': ['Native vehicle body motion',
                            'premises and official access aisle designation review',
                            'parking classification review', 'four original cameras'],
                        'limitations': ['Native diagnostic hatch does not establish official designation',
                            'CPU proof does not claim physical realization or legal verdict']},
                    'status': 'selected_native_cpu_draft_not_delivery_prepared',
                    'static_checks': ['authored OpenDRIVE premises surface',
                        'adjacent aisle and bay extents', '600 original Native frames',
                        'four synchronized FFV1 cameras', 'source-bound body overlap measurement']}
        target = HERE / 'bundles' / suffix / 'construction.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(proposal, indent=2) + '\n')
        entries.append({'case_id': case_id, 'kind': 'delivery',
                        'construction': str(target.relative_to(ROOT)),
                        'construction_sha256': sha(target),
                        'candidate_risk': {'status': 'physical',
                            'reason': 'Native premises geometry, official aisle designation and parking event unverified'},
                        'candidates': [], 'delivery_readiness': 'incomplete'})
    manifest = {'format': 'worker-selected-cpu-draft-manifest-v1',
                'assignment_id': ASSIGNMENT, 'status': 'partial', 'cases': entries,
                'physical_acceptance_claimed': False}
    (ROOT / 'draft-native-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'construction_sha256': [entry['construction_sha256'] for entry in entries]}))


if __name__ == '__main__':
    build()
