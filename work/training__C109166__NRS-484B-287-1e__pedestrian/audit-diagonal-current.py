"""Independent comparison and package readback for unselected diagonal requests."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def main():
    folder = HERE / 'diagnostic-diagonal'
    left = rows(folder / 'controlled_1.jsonl')
    right = rows(folder / 'controlled_2.jsonl')
    if len(left) != len(right) or len(left) != 600:
        raise AssertionError('Complete 600-frame pair missing')
    changes = []
    for i, (a, b) in enumerate(zip(left, right)):
        if a['frame'] != i or b['frame'] != i or a['time_s'] != i / 20 or b['time_s'] != i / 20:
            raise AssertionError('Frame/time join changed')
        if a['pedestrian_xy_m'] != b['pedestrian_xy_m'] or a['footprint_xy_m'] != b['footprint_xy_m']:
            raise AssertionError('Crossing path changed with device intervention')
        if a['device_id'] != b['device_id'] or not a['diagonal_movement_governed'] or not b['diagonal_movement_governed']:
            raise AssertionError('Governing device identity changed')
        if a['device_state'] != b['device_state']:
            changes.append(i)
            if a['device_state'] != 'diagonal_walk' or b['device_state'] != 'diagonal_dont_walk':
                raise AssertionError('Unexpected state intervention')
    if changes != list(range(100, 160)):
        raise AssertionError('Controlled interval does not cover first entry')
    if left[100]['pedestrian_xy_m'] != [-6, -6] or right[340]['pedestrian_xy_m'] != [6, 6]:
        raise AssertionError('Diagonal endpoints changed')
    manifest = json.loads((HERE / 'native/draft-execution-manifest.json').read_text())
    package_checks = []
    for case, entry in zip(('controlled_1', 'controlled_2'), manifest['cases']):
        construction = HERE / 'native' / entry['construction']
        if sha(construction) != entry['construction_sha256']:
            raise AssertionError('Current-runtime construction hash changed')
        bundle = json.loads(construction.read_text())
        sources = {f['path']: f['content'] for f in bundle['files']}
        if (sources['diagonal-source.jsonl'] != (folder / (case + '.jsonl')).read_text() or
                sources['diagonal-context.json'] != (folder / 'context.json').read_text() or
                sources['case-plan.json'] != (HERE / 'case-plan.json').read_text() or
                sources['native_request.py'] != (HERE / 'native/native_request.py').read_text() or
                sources['native-acquisition-contract.json'] !=
                (HERE / 'native/native-acquisition-contract.json').read_text()):
            raise AssertionError('Runtime package differs from reviewed source')
        package_checks.append({'case_suffix': case, 'construction_sha256': sha(construction),
                               'source_sha256': sha(folder / (case + '.jsonl'))})
    receipt = {'format': 'c109166-current-diagonal-independent-audit-v1',
               'joined_frames': 1200, 'changed_device_state_frames': changes,
               'first_entry_states': [left[100]['device_state'], right[100]['device_state']],
               'runtime_packages': package_checks,
               'physical_crossing_observed': False, 'official_device_verified': False,
               'legal_verdict_claimed': False, 'passed': True}
    path = HERE / 'current-diagonal-audit.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'audit_sha256': sha(path)}))


if __name__ == '__main__':
    main()
