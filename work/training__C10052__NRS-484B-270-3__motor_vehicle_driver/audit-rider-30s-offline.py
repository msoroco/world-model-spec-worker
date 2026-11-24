"""Independently check the 30 s rider candidate bindings and offline receipts."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PACKAGE = HERE / 'rider-30s-primary'
sys.path.insert(0, str(HERE / 'native'))
from rider_candidates import parameters  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check():
    manifest = json.loads((PACKAGE / 'draft-manifest.json').read_text())
    assert manifest['status'] == 'draft_not_selected' and len(manifest['cases']) == 1
    entry = manifest['cases'][0]
    assert entry['case_id'] == HERE.name + '__rider_bicycle_clear'
    assert len(entry['candidates']) == 3
    matrix = json.loads((PACKAGE / 'rider-offline-matrix.json').read_text())
    assert matrix['manifest_sha256'] == sha(PACKAGE / 'draft-manifest.json')
    assert matrix['duration_s'] == 30 and matrix['expected_frames'] == 600
    assert len(matrix['receipts']) == 4
    construction_paths = {'primary': entry['construction']}
    digests = {'primary': entry['construction_sha256']}
    for candidate in entry['candidates']:
        construction_paths[candidate['id']] = candidate['construction']
        digests[candidate['id']] = candidate['construction_sha256']
    assert set(construction_paths) == {'primary', 'fallback1', 'fallback2', 'fallback3'}
    baseline_files = None
    baseline_config = None
    changed = {}
    for receipt in matrix['receipts']:
        candidate = receipt['candidate_id']
        construction_path = PACKAGE / construction_paths[candidate]
        assert sha(construction_path) == digests[candidate] == receipt['construction_sha256']
        construction = json.loads(construction_path.read_text())
        assert construction['termination_rules'][0] == '600 original frames'
        files = {item['path']: item['content'] for item in construction['files']}
        config = json.loads(files['config.json'])
        assert config['candidate_id'] == candidate and config['duration_s'] == 30
        assert config['rate_hz'] == 20 and len(config['cameras']) == 4
        assert 'frames!=600' in files['runner.py']
        assert 'len(rider_rows)!=600' in files['finalize_rider.py']
        if candidate == 'primary':
            baseline_files = files
            baseline_config = config
        else:
            assert {name for name in files if files[name] != baseline_files[name]} == {'config.json'}
            assert {key for key in config if config[key] != baseline_config[key]} == {'candidate_id'}
        log = HERE.parents[1] / receipt['log']
        assert sha(log) == receipt['log_sha256']
        outcome = json.loads(log.read_text())
        assert receipt['exit_code'] == 0 and outcome['offline_passed'] is True
        assert outcome['candidate_id'] == candidate and outcome['case_id'] == entry['case_id']
        policy = parameters('bicycle', 'clear', candidate)
        primary = parameters('bicycle', 'clear', 'primary')
        if candidate != 'primary':
            changed[candidate] = [key for key in ('approach_start_x_m',
                                  'release_shift_frames', 'reference_camera_xyz_m')
                                  if policy[key] != primary[key]]
    assert changed == {'fallback1': ['approach_start_x_m'],
                       'fallback2': ['release_shift_frames'],
                       'fallback3': ['reference_camera_xyz_m']}
    result = {'format': 'c10052-rider-30s-offline-independent-audit-v1',
              'case_id': entry['case_id'], 'selected': False, 'accepted': False,
              'manifest_sha256': sha(PACKAGE / 'draft-manifest.json'),
              'matrix_sha256': sha(PACKAGE / 'rider-offline-matrix.json'),
              'construction_sha256': digests, 'isolated_policy_changes': changed,
              'all_four_offline_checks_passed': True,
              'remaining': 'Current source-bound compatibility and saved processing for each candidate'}
    output = PACKAGE / 'rider-offline-matrix-audit.json'
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'audit_sha256': sha(output), 'passed': True}))


if __name__ == '__main__':
    check()
