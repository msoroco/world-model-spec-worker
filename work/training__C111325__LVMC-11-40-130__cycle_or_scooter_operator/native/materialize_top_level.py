"""Materialize a portable top-level CPU construction from selected Native code."""
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent


def main():
    draft = json.loads((FOLDER / 'native/selected-drafts/condition_a/primary/construction.json').read_text())
    manifest = json.loads((FOLDER / 'execution-manifest.json').read_text())
    case_ids = [case['case_id'] for case in manifest['cases']]
    files = []
    for entry in draft['files']:
        target = FOLDER / entry['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        content = entry['content']
        if entry['path'] == 'config.json':
            config = json.loads(content)
            config['supported_case_ids'] = case_ids
            for camera in config['cameras']:
                camera['pose_strategy'] = 'surveyed bicycle, stop sign and approach interval'
                camera['fov_deg'] = 90
            content = json.dumps(config, indent=2) + '\n'
        if entry['path'] == 'tests/test_exact.py':
            content = ('import unittest\n'
                       'from runner import check\n\n'
                       'class ExactBicycleConstruction(unittest.TestCase):\n'
                       '    def test_cpu_selected_check(self):\n'
                       '        result = check()\n'
                       '        self.assertTrue(result["passed"])\n'
                       '        self.assertEqual(result["frames"], 600)\n'
                       '        self.assertFalse(result["original_native_executed"])\n')
        target.write_text(content)
        files.append({'path': entry['path'], 'source': 'work/' + FOLDER.name + '/' + entry['path'],
                      'content': content})
    draft['files'] = files
    draft['supported_case_ids'] = case_ids
    draft['static_checks'] = ['selected Native setup and survey', '600-frame source/camera join',
                              'original legal prudence remains unresolved']
    draft['termination_rules'] = {'frames': 600, 'rate_hz': 20,
                                  'on_source_gap': 'reject attempt, do not infer a legal outcome'}
    draft['mechanisms'] = ['authored stop-sign approach', 'original bicycle velocity readback',
                           'four synchronized RGB cameras', 'recorded-only saved finalization']
    (FOLDER / 'construction.json').write_text(json.dumps(draft, indent=2) + '\n')
    print(json.dumps({'materialized_files': len(files), 'selected_cases': len(case_ids)}))


if __name__ == '__main__':
    main()
