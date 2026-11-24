"""Materializable current-runtime draft for the source-bound selected cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def emit(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def build():
    root = json.loads((HERE / 'construction.json').read_text())
    root_config = json.loads((HERE / 'config.json').read_text())
    risk = {item['case_suffix']: item for item in
            json.loads((HERE / 'risk-selection.json').read_text())['cases']}
    candidates = {'reference': ('primary',),
                  'contrast': ('primary', 'fallback1', 'fallback2')}
    entries = []
    for suffix, variants in candidates.items():
        case_id = HERE.name + '__' + suffix
        built = {}
        for variant in variants:
            source = HERE / 'offline' / suffix / variant
            config = json.loads((source / 'config.json').read_text())
            config.update(selected_case_id=case_id, case={'case_id': case_id},
                          supported_case_ids=root_config['supported_case_ids'],
                          required_atoms=[], source_packets=[],
                          cameras=root_config['cameras'],
                          recording_description=root['recording_description'])
            finalizer = ('native/finalize_v2.py' if suffix == 'reference' else
                         'native/finalize_v2_contrast.py')
            inventory = {'runner.py': HERE / 'native/runner.py',
                         'finalize.py': HERE / finalizer}
            for name in ('assignment-source.json', 'case-plan.json',
                         'road.xodr', 'requested-tracks.jsonl',
                         'measure_saved.py', 'measure_camera.py',
                         'measure_context.py', 'prepare_context.py',
                         'measure_exception.py', 'measurement-contract.json',
                         'triggers.py'):
                inventory[name] = source / name
            files = [{'path': name, 'content': path.read_text()}
                     for name, path in inventory.items()]
            files.append({'path': 'config.json',
                          'content': json.dumps(config, indent=2, sort_keys=True) + '\n'})
            test = '''"""Run the materialized exact Native request check."""
import json
from pathlib import Path
import subprocess
import sys
import unittest


class ExactRequestTest(unittest.TestCase):
    def test_materialized_native_request(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, str(root / 'runner.py'), '--check'],
                                capture_output=True, text=True, check=True)
        value = json.loads(result.stdout)
        self.assertEqual(value['requested_frames'], 600)
        self.assertFalse(value['original_native_observed'])

    def test_original_input_hash(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / 'config.json').read_text())
        self.assertEqual(config['duration_s'], 30)
        self.assertEqual(config['selected_case_id'], config['case_id'])
'''
            files.append({'path': 'tests/test_cpu.py', 'content': test})
            construction = {key: root[key] for key in
                            ('cell_id', 'law_id', 'actor', 'entrypoint',
                             'recording_description', 'measurement_plan',
                             'static_checks', 'termination_rules', 'mechanisms')}
            construction.update(case_id=case_id, files=files,
                                status='selected_draft_pending_proofs')
            path = HERE / ('selected-' + suffix + '-' + variant + '-construction.json')
            emit(path, construction)
            built[variant] = {'id': variant, 'construction': path.name,
                              'construction_sha256': digest(path)}
        primary = built['primary']
        risk_item = risk[suffix]
        entry = {'case_id': case_id, 'kind': 'delivery',
                 'id': 'primary', 'construction': primary['construction'],
                 'construction_sha256': primary['construction_sha256'],
                 'measurement_contract': 'v2-' + suffix + '-primary-measurement-contract.json',
                 'measurement_procedure': {'entrypoint': 'finalize.py'},
                 'fixture_recipe': str((HERE / ('selected-' + suffix + '-fixture-recipe.json')).relative_to(REPO)),
                 'candidate_risk': {'status': risk_item['candidate_risk_status'],
                                    'reason': risk_item['physical_risk']},
                 'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                    'host_env_var': 'CARLA_HOST',
                                    'port_env_var': 'CARLA_PORT'},
                 'candidates': []}
        for selected in risk_item['selected_fallbacks']:
            variant = selected['candidate_id']
            item = dict(built[variant])
            item['trigger'] = {'source': selected['trigger_source'],
                               'metric': selected['metric'],
                               'failure_condition': selected['failure_condition']}
            item['changed_knobs'] = [selected['engineering_change']]
            entry['candidates'].append(item)
        entries.append(entry)
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': HERE.name,
                'runtime_manifest_sha256': digest(REPO / 'runtime/SOURCE-MANIFEST.json'),
                'status': 'partial_selected_draft', 'delivery_ready': False,
                'original_native_observed': False, 'cases': entries}
    emit(HERE / 'selected-draft-execution-manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    print(json.dumps({'cases': len(build()['cases'])}))
