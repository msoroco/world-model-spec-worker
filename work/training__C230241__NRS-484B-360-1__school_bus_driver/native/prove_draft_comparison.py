"""Check exact two-probe isolation without treating requested speed as observed."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = ROOT / 'draft-primary-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    assert len(manifest['cases']) == 2
    configs = []
    constructions = []
    for entry in manifest['cases']:
        path = ROOT / entry['construction']
        assert sha(path) == entry['construction_sha256']
        construction = json.loads(path.read_text())
        assert construction['case_id'] == entry['case_id']
        files = {item['path']: item['content'] for item in construction['files']}
        assert set(files) == {'runner.py', 'controller.py', 'config.json',
                              'tests/test_offline.py'}
        configs.append(json.loads(files['config.json']))
        constructions.append((entry, files))
    first, second = configs
    assert first['requested_speed_mph'] == 52
    assert second['requested_speed_mph'] == 58
    for key in first:
        if key not in ('case_id', 'requested_speed_mph'):
            assert first[key] == second[key], key
    for key in ('runner.py', 'controller.py', 'tests/test_offline.py'):
        assert constructions[0][1][key] == constructions[1][1][key], key
    result = {
        'format': 'c230241-unselected-speed-probe-audit-v1',
        'passed': True, 'selected': False,
        'manifest_sha256': sha(manifest_path),
        'construction_sha256': [entry['construction_sha256']
                                for entry, _ in constructions],
        'fixed': ['law', 'cell', 'actor', 'ice_cream_truck_control', 'route_spawn',
                  'four_camera_profile', '30_second_20_hz_window', 'controller_code',
                  'source_measurement_contract'],
        'deliberate_difference': {'requested_speed_mph': [52, 58]},
        'actual_speed_observed': False,
        'pupils_aboard_observed': False,
        'legal_verdict_claimed': False,
        'limitations': ['Exact Native assets, pupil occupancy and school trip purpose '
                        'remain subject to original source and independent review.'],
    }
    path = ROOT / 'draft-comparison-audit.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'audit': str(path), 'sha256': sha(path), 'passed': True}))


if __name__ == '__main__':
    main()
