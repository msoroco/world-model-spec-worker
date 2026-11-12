"""Verify the three exact draft constructions and their offline CPU receipts."""

import hashlib
import json
from pathlib import Path

from through_speed_sweep import TARGETS_MPS

ROOT = Path(__file__).resolve().parent


def main():
    manifest = json.loads((ROOT / 'through-speed-draft-manifest.json').read_text())
    assert len(manifest['cases']) == len(TARGETS_MPS)
    normalized = []
    receipts = []
    for target, entry in zip(TARGETS_MPS, manifest['cases']):
        speed = int(target)
        suffix = f'yield_nearest_view_through_speed_{speed}'
        path = ROOT / entry['construction']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['construction_sha256']
        construction = json.loads(path.read_text())
        assert construction['case_id'] == entry['case_id']
        files = {item['path']: item['content'] for item in construction['files']}
        assert f'THROUGH_TARGET_MPS = {target:.1f}' in files['yield_motion.py']
        config = json.loads(files['config.json'])
        assert config['selected_case_id'] == entry['case_id']
        assert entry['case_id'] in config['supported_case_ids']
        assert "if suffix != 'yield_nearest_view_clear':" in files['yield_construction.py']
        log = ROOT / f'cases/through_speed_{speed}/offline.log'
        assert log.read_text().strip()
        materialized = ROOT.parents[1] / f'.runtime-work/c158190-through-speed-{speed}-offline-v2'
        offline = (materialized / 'offline.log').read_text()
        assert 'Ran 34 tests' in offline and 'OK' in offline
        assert (materialized / 'yield_motion.py').read_text() == files['yield_motion.py']
        assert (materialized / 'runner.py').read_text() == files['runner.py']
        snapshot = {}
        for name, content in files.items():
            if name in ('config.json', 'yield_motion.py', 'tests/test_yield_motion.py'):
                continue
            snapshot[name] = content.replace(suffix, 'SPEED_CASE')
        normalized.append(snapshot)
        receipts.append({'case_id': entry['case_id'], 'target_mps': target,
                         'construction_sha256': entry['construction_sha256'],
                         'offline_log_sha256': hashlib.sha256(log.read_bytes()).hexdigest(),
                         'materialized_test_count': 34})
    assert normalized[0] == normalized[1] == normalized[2]
    output = {'format': 'c158190-through-speed-exact-offline-proof',
              'cases': receipts, 'fixed_embedded_files_identical_except_case_and_target': True,
              'native_feasibility_proven': False,
              'selected_delivery_manifest_changed': False}
    (ROOT / 'through-speed-exact-offline-proof.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'passed': True, 'exact_cases': len(receipts), 'offline_tests_each': 34}))


if __name__ == '__main__':
    main()
