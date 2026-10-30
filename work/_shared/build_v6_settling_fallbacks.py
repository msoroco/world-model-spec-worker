"""Build a pre-capture physics settling fallback for exact delivery cases.

The fallback changes only the number of stationary Native world ticks before
sensor creation and the recorded interval. This addresses spawn suspension
transients without changing law, actors, scene, controller targets, observations,
case variables, or the synchronized capture duration.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')

def main():
    count = 0
    for manifest_path in sorted((ROOT / 'work').glob('testing__*/execution-manifest.json')):
        folder = manifest_path.parent
        manifest = json.loads(manifest_path.read_text())
        for entry in manifest['cases']:
            case_id = entry['case_id']
            if entry.get('candidates'):
                raise ValueError('Fallback already authored and proof-bound: ' + case_id)
            construction = json.loads((folder / entry['construction']).read_text())
            sources = {row['path']: row for row in construction['files']}
            runner = sources['runner.py']['content']
            old = 20 if 'for _ in range(20):\n            world.tick()' in runner else 30
            needle = f'for _ in range({old}):\n            world.tick()'
            if runner.count(needle) != 1 or runner.count('def check():') != 1:
                raise ValueError('No unique stationary startup path: ' + case_id)
            new = old + 20
            runner = runner.replace('def check():', f'def startup_settling_ticks():\n    return {new}\n\ndef check():', 1)
            runner = runner.replace(needle, 'for _ in range(startup_settling_ticks()):\n            world.tick()', 1)
            tests = sources['tests/test_case.py']['content']
            tests += ('\nimport unittest\n\nclass StartupSettlingFallbackTest(unittest.TestCase):\n'
                      f'    def test_stationary_native_warmup(self):\n        import runner\n        self.assertEqual(runner.startup_settling_ticks(), {new})\n')
            suffix = case_id[len(manifest['assignment_id']) + 2:]
            target = folder / 'fallbacks' / suffix
            target.mkdir(parents=True, exist_ok=True)
            (target / 'runner.py').write_text(runner)
            (target / 'test_settling.py').write_text(tests)
            sources['runner.py']['content'] = runner
            sources['runner.py']['source'] = str((target / 'runner.py').relative_to(ROOT))
            sources['tests/test_case.py']['content'] = tests
            sources['tests/test_case.py']['source'] = str((target / 'test_settling.py').relative_to(ROOT))
            candidate_path = target / 'construction.json'
            save(candidate_path, construction)
            entry['candidate_risk'] = {
                'status': 'physical',
                'reason': 'Native vehicle spawn suspension or hitch settling can contaminate the first captured body positions and velocities.'}
            entry['candidates'] = [{
                'id': 'fallback1',
                'construction': str(candidate_path.relative_to(folder)),
                'construction_sha256': sha(candidate_path),
                'trigger': {
                    'source': 'capture/evidence.jsonl',
                    'metric': 'first_second_subject_vertical_centroid_range_m',
                    'failure_condition': 'value_m > 0.05',
                    'script': 'work/_shared/fallback_trigger.py'
                },
                'changed_knobs': [f'stationary pre-capture Native settling ticks: {old} to {new}; capture tick count and all case controls unchanged']
            }]
            count += 1
        save(manifest_path, manifest)
    print(json.dumps({'built': count, 'physical_change': 'stationary pre-capture settling +20 Native ticks'}))

if __name__ == '__main__':
    main()
