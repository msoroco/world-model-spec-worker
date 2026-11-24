"""Independent source and package comparison audit for diagonal authorization."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def main():
    source_dir = HERE / 'diagnostic-authorization'
    a = rows(source_dir / 'probe_01.jsonl')
    b = rows(source_dir / 'probe_02.jsonl')
    if len(a) != 600 or len(b) != 600:
        raise AssertionError('30-second pair incomplete')
    changed = []
    length = 0.0
    previous = None
    for index, (left, right) in enumerate(zip(a, b)):
        if left['frame'] != index or right['frame'] != index or \
                left['time_s'] != index / 20 or right['time_s'] != index / 20:
            raise AssertionError('Frame/time join differs')
        for key in ('pedestrian_xy_m', 'footprint_xy_m', 'device_id', 'source_kind'):
            if left[key] != right[key]:
                raise AssertionError('Controlled route/device identity changed')
        center = left['pedestrian_xy_m']
        body = left['footprint_xy_m']
        if len(body) != 4 or any(abs(sum(v[k] for v in body) / 4 - center[k]) > 1e-8
                                 for k in (0, 1)):
            raise AssertionError('Full body does not track center')
        if previous is not None:
            length += math.dist(previous, center)
        previous = center
        if left['requested_diagonal_authorization'] != right['requested_diagonal_authorization']:
            changed.append(index)
            if left['requested_diagonal_authorization'] is not True or \
                    right['requested_diagonal_authorization'] is not False:
                raise AssertionError('Unexpected authorization control')
    if len(changed) != 600 or a[100]['pedestrian_xy_m'] != [-6, -6] or \
            a[340]['pedestrian_xy_m'] != [6, 6] or not 16.9 < length < 17.1:
        raise AssertionError('Controlled diagonal path/authorization changed')
    manifest = json.loads((HERE / 'native/draft-execution-manifest.json').read_text())
    packages = []
    for suffix, entry in zip(('probe_01', 'probe_02'), manifest['cases']):
        path = HERE / 'native' / entry['construction']
        if sha(path) != entry['construction_sha256']:
            raise AssertionError('Construction hash changed')
        construction = json.loads(path.read_text())
        files = {row['path']: row['content'] for row in construction['files']}
        if (files['diagonal-source.jsonl'] != (source_dir / (suffix + '.jsonl')).read_text() or
                files['case-plan.json'] != (HERE / 'case-plan.json').read_text()):
            raise AssertionError('Package source differs from retained pair')
        packages.append({'case_suffix': suffix, 'construction_sha256': sha(path),
                         'source_sha256': sha(source_dir / (suffix + '.jsonl'))})
    receipt = {'format': 'c109166-1d-independent-authorization-audit-v1',
               'joined_frames': 1200, 'changed_authorization_frames': len(changed),
               'first_entry_authorization': [a[100]['requested_diagonal_authorization'],
                                             b[100]['requested_diagonal_authorization']],
               'path_length_m': round(length, 6), 'packages': packages,
               'official_device_verified': False, 'physical_crossing_observed': False,
               'legal_verdict_claimed': False, 'passed': True}
    target = HERE / 'authorization-independent-audit.json'
    target.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'audit_sha256': sha(target)}))


if __name__ == '__main__':
    main()
