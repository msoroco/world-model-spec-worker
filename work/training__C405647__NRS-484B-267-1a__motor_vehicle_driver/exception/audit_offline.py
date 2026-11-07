"""Independent source and receipt audit for exact officer-exception offline runs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest_path = HERE / 'package-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    summary = json.loads((HERE / 'cpu-summary.json').read_text())
    assert summary['manifest_sha256'] == sha(manifest_path)
    assert manifest['status'] == 'draft_not_selected'
    assert len(manifest['cases']) == 2 and len(summary['receipts']) == 8
    seen = set()
    for case in manifest['cases']:
        assert case['kind'] == 'draft_not_selected'
        refs = [case] + case['candidates']
        assert {r['id'] for r in refs} == {'primary', 'fallback1', 'fallback2', 'fallback3'}
        for ref in refs:
            candidate = ref['id']
            key = case['case_id'], candidate
            assert key not in seen
            seen.add(key)
            construction = HERE / ref['construction']
            assert sha(construction) == ref['construction_sha256']
            proposal = json.loads(construction.read_text())
            assert proposal['case_id'] == case['case_id']
            assert proposal['entrypoint'] == 'runner.py'
            files = {item['path']: item['content'] for item in proposal['files']}
            assert {'config.json', 'runner.py', 'build.py', 'official_motion.py',
                    'candidates.py',
                    'statutory-scope.json', 'tests/test_construction.py'} <= files.keys()
            config = json.loads(files['config.json'])
            assert config['case_id'] == case['case_id']
            assert config['candidate_id'] == candidate
            assert config['officer_direction_verified'] is False
            assert config['physical_success_claimed'] is False
            for name in ('runner.py', 'build.py', 'official_motion.py',
                         'candidates.py', 'statutory-scope.json'):
                assert files[name] == (HERE / name).read_text()
            folder = HERE / 'cpu-receipts' / case['case_id'].rsplit('__', 1)[1] / candidate
            receipt = json.loads((folder / 'receipt.json').read_text())
            assert receipt['case_id'] == key[0] and receipt['candidate_id'] == key[1]
            assert receipt['construction_sha256'] == ref['construction_sha256']
            assert receipt['exit_code'] == 0 and receipt['simulation_started'] is False
            assert receipt['command_log_sha256'] == sha(folder / 'command.log')
            assert receipt['unit_log_sha256'] == sha(folder / 'offline.log')
            log = (folder / 'offline.log').read_text()
            assert 'Ran 2 tests' in log and '\nOK\n' in log
            assert '"carla_imported": false' in log and '"native_track_rows": 480' in log
            assert '"camera_count": 5' in log
            assert key in {(r['case_id'], r['candidate_id']) for r in summary['receipts']}
    return {'passed': True, 'exact_offline_receipts': len(seen),
            'native_or_original_observation_verified': False,
            'portable_compatibility_verified': False}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
