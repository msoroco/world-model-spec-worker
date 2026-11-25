"""Bind two exact crosswalk cases to current Native code and selected drafts."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def build():
    entries = []
    source_names = {
        'runner.py': 'native/runner.py',
        'live_capture.py': 'native/live_capture.py',
        'measure_stop.py': 'native/measure_stop.py',
        'finalize.py': 'native/finalize.py',
        'authored-road.xodr': 'native/road.xodr',
    }
    for index in (1, 2):
        case = HERE.name + f'__probe_{index}'
        draft = json.loads((HERE / f'draft-probe-{index}/construction.json').read_text())
        sources = {item['path']: item['content'] for item in draft['files']}
        for name, local in source_names.items():
            sources[name] = (HERE / local).read_text()
        config = json.loads(sources['config.json'])
        config['status'] = 'selected_cpu_delivery_draft'
        config['physical_completion'] = {
            'criterion': 'intersection_clearance',
            'motion_source': 'stop_history.jsonl',
            'body_key': 'body_vertices_m',
            'context_sources': ['crosswalk_geometry.json'],
            'exit_axis': 1, 'exit_sign': 1,
        }
        sources['config.json'] = json.dumps(config, indent=2) + '\n'
        test = '''import json\nfrom pathlib import Path\nimport unittest\nfrom runner import check\nfrom live_capture import requested_speed, START_Y\n\nclass ExactCase(unittest.TestCase):\n    def test_identity_and_geometry(self):\n        config=json.loads(Path('config.json').read_text())\n        self.assertTrue(check(config)['passed'])\n        self.assertEqual(config['case_id'], config['selected_case_id'])\n        self.assertLess(START_Y,-40)\n    def test_control_is_request(self):\n        case=json.loads(Path('config.json').read_text())['case_id']\n        expected=0 if case.endswith('probe_1') else 4\n        self.assertEqual(requested_speed(140,case,-18),expected)\n        with self.assertRaises(ValueError):requested_speed(600,case,-18)\n\nif __name__=='__main__':unittest.main()\n'''
        sources['tests/test_exact.py'] = test
        sources.pop('tests/test_primary.py', None)
        construction = {
            'actor': draft['actor'], 'case_id': case,
            'cell_id': draft['cell_id'], 'law_id': draft['law_id'],
            'entrypoint': 'runner.py',
            'files': [{'path': name, 'content': content} for name, content in sorted(sources.items())],
            'recording_description': draft['recording_description'],
            'measurement_plan': {'method': 'source-hashed original body and stop-before-boundary measurement',
                                 'status': 'selected_cpu_draft'},
            'static_checks': ['600 frame/time joins', 'four original source cameras',
                              'signed subject lane and near-side crosswalk road source'],
            'termination_rules': ['retain exact original frames or an explicit failed acquisition',
                                  'close encoders and restore the operator world'],
            'mechanisms': ['20 Hz original Native capture', 'four synchronized camera views',
                           'source-bound stop/body measurement'],
            'status': 'selected_cpu_delivery_draft',
        }
        primary = HERE / f'selected-probe-{index}-primary-construction.json'
        write(primary, construction)
        fallback = deepcopy(construction)
        for item in fallback['files']:
            if item['path'] == 'live_capture.py':
                if 'START_Y = -50.0' not in item['content']:
                    raise ValueError('Expected primary spawn binding missing')
                item['content'] = item['content'].replace('START_Y = -50.0', 'START_Y = -55.0')
        alternate = HERE / f'selected-probe-{index}-fallback1-construction.json'
        write(alternate, fallback)
        entries.append({
            'case_id': case, 'kind': 'delivery',
            'construction': primary.name, 'construction_sha256': sha(primary),
            'fixture_recipe': f'work/{HERE.name}/current-v2-probe-{index}-fixture-recipe.json',
            'measurement_contract': f'current-v2-probe-{index}-measurement-contract.json',
            'measurement_procedure': {'entrypoint': 'finalize.py'},
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
            'candidate_risk': {'status': 'physical',
                               'reason': 'Original braking may carry the full body across the near-side crosswalk margin'},
            'candidates': [{
                'id': 'fallback1', 'construction': alternate.name,
                'construction_sha256': sha(alternate),
                'changed_knobs': ['move original subject spawn 5 m farther from the crosswalk'],
                'trigger': {'source': 'native_samples.jsonl',
                            'metric': 'first_crosswalk_body_frame',
                            'failure_condition': 'full body crosses before requested stop window or source window ends'},
            }],
        })
    manifest = HERE / 'selected-draft-execution-manifest.json'
    write(manifest, {'format': 'worker-execution-manifest',
                     'assignment_id': HERE.name,
                     'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
                     'status': 'selected_cpu_draft', 'cases': entries})
    return {'manifest_sha256': sha(manifest), 'case_count': len(entries)}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
