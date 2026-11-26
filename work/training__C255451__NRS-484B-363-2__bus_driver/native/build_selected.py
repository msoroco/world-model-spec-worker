"""Freeze eight exact bus school-zone capture bundles from one reviewed template.

This builds code and configuration only. It does not claim an original recording
or source review. The lead binds receipts after the independent CPU proofs pass.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parents[1]
PREFIX = ROOT.name + '__selected_d08892c9__'
CONDITIONS = {
    'condition_a': (20, 'beacon_active'),
    'at_limit': (25, 'beacon_active'),
    'condition_b': (30, 'beacon_active'),
    'no_school_day': (30, 'no_school_day'),
    'half_hour_window': (30, 'half_hour_window'),
    'beacon_not_flashing': (30, 'beacon_not_flashing'),
    'nonbeacon_sign_active': (30, 'nonbeacon_sign_active'),
    'nonbeacon_sign_inactive': (30, 'nonbeacon_sign_inactive'),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    template = HERE / 'selected_primary'
    original_case_suffix = '__selected_d08892c9__condition_b'
    sources = {name: (template / name).read_text() for name in
               ('runner.py', 'finalize.py', 'tests/test_bundle.py')}
    sources['measure_saved.py'] = (HERE / 'measure_saved.py').read_text()
    base = json.loads((template / 'config.json').read_text())
    entries = []
    for name, (target_mph, planned_context) in CONDITIONS.items():
        case_id = PREFIX + name
        config = json.loads(json.dumps(base))
        config['case_id'] = case_id
        config['selected_case_id'] = case_id
        config['case']['case_id'] = case_id
        config['target_mph'] = target_mph
        config['planned_context'] = planned_context
        files = [{'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'}]
        for filename, content in sources.items():
            files.append({'path': filename,
                          'content': content.replace(
                              original_case_suffix, '__selected_d08892c9__' + name)})
        construction = {
            'format': 'worker-inline-construction',
            'case_id': case_id,
            'cell_id': 'C255451',
            'actor': 'bus_driver',
            'entrypoint': 'runner.py',
            'files': files,
            'recording_description': config['recording_description'],
            'status': 'selected_cpu_construction_pending_proofs',
        }
        path = HERE / 'selected' / name / 'construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(construction, indent=2) + '\n')
        entries.append({'case_id': case_id,
                        'construction': str(path.relative_to(ROOT)),
                        'construction_sha256': sha(path),
                        'kind': 'delivery',
                        'candidate_risk': {'status': 'none',
                                           'reason': 'No original Native failure trigger has yet been measured.'},
                        'candidates': [],
                        'delivery_readiness': 'incomplete',
                        'measurement_procedure': {'entrypoint': 'finalize.py',
                                                  'output_schema': 'c255451-school-zone-analysis-v1'},
                        'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                           'host_env_var': 'CARLA_HOST',
                                           'port_env_var': 'CARLA_PORT'}})
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': ROOT.name,
                'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
                'status': 'partial', 'cases': entries}
    (ROOT / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return {'cases': len(entries), 'construction_sha256':
            {item['case_id']: item['construction_sha256'] for item in entries}}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
