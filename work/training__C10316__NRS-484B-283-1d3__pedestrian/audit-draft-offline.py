"""Independent source, controlled-input, and pinned offline receipt audit."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/pipeline'))
from scenario_pipeline.worker_exchange.candidate_constructions import validate


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    batch = json.loads((ROOT / 'batch.json').read_text())
    assert manifest['runtime_manifest_sha256'] == batch['runtime']['source_manifest_sha256']
    assert manifest['status'] == 'draft_not_selected' and len(manifest['cases']) == 2
    summary = json.loads((HERE / 'draft-offline-summary.json').read_text())
    assert summary['runtime_manifest_sha256'] == manifest['runtime_manifest_sha256']
    assert len(summary['results']) == 8
    sources = ('runner.py', 'geometry.py', 'engineering.py', 'no_countdown.py',
               'finalize.py', 'road.xodr')
    configs = {}
    seen = set()
    for case in manifest['cases']:
        validate(HERE, case, 'NRS-484B-283-1d3', 'C10316', required=False, candidate_count=4)
        suffix = case['case_id'].rsplit('__', 1)[-1]
        configs[suffix] = {}
        for ident in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            selected = case if ident == 'primary' else next(x for x in case['candidates'] if x['id'] == ident)
            path = HERE / selected['construction']
            assert sha(path) == selected['construction_sha256']
            construction = json.loads(path.read_text())
            files = {item['path']: item['content'] for item in construction['files']}
            for name in sources:
                assert files[name] == (HERE / 'native' / name).read_text()
            assert files['tests/test_offline.py'] == (HERE / 'native/test_offline.py').read_text()
            config = json.loads(files['config.json'])
            assert config['case_id'] == case['case_id'] == config['selected_case_id']
            assert config['candidate_id'] == ident
            assert (config['duration_s'], config['rate_hz']) == (12, 20)
            assert (config['law_id'], config['cell_id'], config['actor']) == ('NRS-484B-283-1d3', 'C10316', 'pedestrian')
            assert config['required_atoms'] == ['ru.pedestrian', 'kin.position', 'kin.heading', 'st.crosswalk', 'rel.occupies']
            assert len(config['cameras']) == 4
            configs[suffix][ident] = config
            receipt = json.loads((path.parent / 'draft-receipt.json').read_text())
            assert receipt['case_id'] == case['case_id'] and receipt['candidate_id'] == ident
            assert receipt['construction_sha256'] == selected['construction_sha256']
            assert receipt['exit_code'] == 0
            assert sha(HERE / receipt['command_log']) == receipt['command_log_sha256']
            assert sha(HERE / receipt['unit_log']) == receipt['unit_log_sha256']
            assert 'Ran 4 tests' in (HERE / receipt['unit_log']).read_text()
            assert '\nOK' in (HERE / receipt['unit_log']).read_text()
            assert 'simulation_started' in (HERE / receipt['command_log']).read_text()
            assert receipt in summary['results']
            seen.add((case['case_id'], ident))
    assert len(seen) == 8
    for suffix, candidates in configs.items():
        base = candidates['primary']
        for ident, value in candidates.items():
            compared = dict(value)
            compared['candidate_id'] = 'primary'
            assert compared == base
    for ident in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        a = dict(configs['controlled_1'][ident])
        b = dict(configs['controlled_2'][ident])
        for item in (a, b):
            for key in ('case_id', 'selected_case_id', 'case', 'case_suffix'):
                item.pop(key)
        assert a == b
    print(json.dumps({'audit': 'pass', 'unselected_exact_offline_bundles': 8,
                      'runtime_hash_bound': True, 'same_capture_contract': True,
                      'selected_cases': 0, 'accepted_recordings': 0}))


if __name__ == '__main__':
    main()
