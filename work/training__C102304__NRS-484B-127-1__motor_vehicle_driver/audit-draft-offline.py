"""Independent exact construction/source/receipt audit for eight CPU drafts."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'runtime'/'pipeline'))
from scenario_pipeline.worker_exchange.candidate_constructions import validate


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE/'draft-execution-manifest.json').read_text())
    batch = json.loads((ROOT/'batch.json').read_text())
    assert manifest['runtime_manifest_sha256'] == batch['runtime']['source_manifest_sha256']
    assert manifest['status'] == 'draft_not_selected'
    assert len(manifest['cases']) == 2
    summary = json.loads((HERE/'draft-offline-summary.json').read_text())
    assert len(summary['results']) == 8
    seen = set()
    for case in manifest['cases']:
        validate(HERE, case, 'NRS-484B-127-1', 'C102304', required=False, candidate_count=4)
        configs = {}
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            selected = case if candidate == 'primary' else next(
                row for row in case['candidates'] if row['id'] == candidate)
            construction_path = HERE/selected['construction']
            assert sha(construction_path) == selected['construction_sha256']
            construction = json.loads(construction_path.read_text())
            files = {item['path']: item['content'] for item in construction['files']}
            for name in ('runner.py','geometry.py','engineering.py','measure_following.py','finalize.py'):
                assert files[name] == (HERE/'native'/name).read_text()
            config = json.loads(files['config.json'])
            assert config['case_id'] == case['case_id'] == config['selected_case_id']
            assert config['candidate_id'] == candidate
            assert config['duration_s'] == 45 and config['rate_hz'] == 20
            assert config['required_atoms'] == ['kin.speed','st.lane','rel.surface_gap','rel.ahead_behind_in_lane']
            configs[candidate] = config
            folder = construction_path.parent
            receipt = json.loads((folder/'draft-receipt.json').read_text())
            assert receipt['case_id'] == case['case_id'] and receipt['candidate_id'] == candidate
            assert receipt['construction_sha256'] == selected['construction_sha256']
            assert receipt['exit_code'] == 0
            assert sha(HERE/receipt['command_log']) == receipt['command_log_sha256']
            assert sha(HERE/receipt['unit_log']) == receipt['unit_log_sha256']
            log = (HERE/receipt['unit_log']).read_text()
            assert 'Ran 4 tests' in log and '\nOK' in log
            assert 'simulation_started' in (HERE/receipt['command_log']).read_text()
            assert receipt in summary['results']
            seen.add((case['case_id'], candidate))
        base = configs['primary']
        for candidate in ('fallback1','fallback2','fallback3'):
            compare = dict(configs[candidate])
            compare['candidate_id'] = 'primary'
            assert compare == base
    assert len(seen) == 8
    print(json.dumps({'audit': 'pass', 'cases': 2, 'exact_offline_bundles': 8,
                      'runtime_hash_bound': True, 'selected_cases': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
