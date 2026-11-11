"""Check all selected rider fallback packages against pinned candidate rules."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.candidate_constructions import validate


def check():
    checks = []
    for manifest_name in ('first-execution-manifest.json', 'no-signal-manifest.json',
                          'continuous-manifest.json', 'electric-bicycle-manifest.json',
                          'electric-scooter-manifest.json'):
        entry = json.loads((FOLDER / manifest_name).read_text())['cases'][0]
        verified = validate(FOLDER, entry, 'NRS-484B-768-1', 'C111588',
                            required=True, require_alternate=True, candidate_count=4)
        primary = json.loads((FOLDER / entry['construction']).read_text())
        primary_files = {item['path']: item['content'] for item in primary['files']}
        expected = {'fallback1': {'rider_route.py'},
                    'fallback2': {'runner.py', 'native_rider_probe.py'},
                    'fallback3': {'rider_camera.py'}}
        for candidate in entry['candidates']:
            alternate = json.loads((FOLDER / candidate['construction']).read_text())
            changed = {item['path'] for item in alternate['files']
                       if item['content'] != primary_files[item['path']]}
            if changed != expected[candidate['id']]:
                raise ValueError('Fallback changed unexpected source files: ' + candidate['id'])
        checks.append(verified)
    return {'candidate_sets': checks, 'distinct_physical_knobs_checked': True,
            'physical_effectiveness_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
