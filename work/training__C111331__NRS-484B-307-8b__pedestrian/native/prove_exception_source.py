"""Construct the distinct other-device permission branch as a CPU diagnostic."""
import hashlib
import json
from pathlib import Path

from red_entry import FRAMES, requested


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))


def analyze(path, permission):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines()]
    baseline = requested('condition_b')
    if len(rows) != FRAMES:
        raise ValueError('Exact entry source missing')
    highway = []
    permitted = []
    for i, (row, base) in enumerate(zip(rows, baseline)):
        if row['frame'] != i or row['time_s'] != i/20:
            raise ValueError('Frame/time join changed')
        for key in ('pedestrian_center_xy_m', 'pedestrian_footprint_xy_m',
                    'signal_id', 'signal_state', 'source_kind',
                    'original_native_observed', 'legal_verdict'):
            if row[key] != base[key]:
                raise ValueError('Controlled entry or signal source changed')
        if row['signal_state'] != 'steady_red_alone':
            raise ValueError('Steady-red branch changed')
        if row['other_device_id'] != ('other_device_283' if permission else None):
            raise ValueError('Other-device identity changed')
        if row['other_device_permits'] is not permission:
            raise ValueError('Other-device permission changed')
        if row['other_device_authority_native_verified'] is not False:
            raise ValueError('Unverified device authority claimed')
        if min(point[1] for point in row['pedestrian_footprint_xy_m']) < 2.0:
            highway.append(i)
            if row['other_device_permits']:
                permitted.append(i)
    if not highway or (len(permitted) == len(highway)) != permission:
        raise ValueError('Entry/permission branch contrast changed')
    return {'frames': len(rows), 'first_highway_frame': highway[0],
            'highway_frames': len(highway),
            'entry_frames_with_authored_permission': len(permitted),
            'other_device_authority_native_verified': False,
            'source_sha256': sha(path)}


def main():
    assignment = Path(__file__).resolve().parents[1]
    folder = assignment/'diagnostic-red-entry'
    base = requested('condition_b')
    results = {}
    for name, permission in (('exception_absent', False),
                             ('exception_permits', True)):
        rows = []
        for original in base:
            row = dict(original)
            row['other_device_id'] = 'other_device_283' if permission else None
            row['other_device_permits'] = permission
            row['other_device_authority_native_verified'] = False
            rows.append(row)
        path = folder/(name+'.jsonl')
        write_rows(path, rows)
        results[name] = analyze(path, permission)
    if results['exception_absent']['first_highway_frame'] != \
            results['exception_permits']['first_highway_frame']:
        raise ValueError('Entry path comparison changed')
    changed = folder/'exception_permits.jsonl'
    rows = [json.loads(line) for line in changed.read_text().splitlines()]
    rows[205]['other_device_permits'] = False
    test = assignment.parents[1]/'.runtime-work/c111331-exception-negative.jsonl'
    test.parent.mkdir(parents=True, exist_ok=True)
    write_rows(test, rows)
    try:
        analyze(test, True)
    except ValueError as exc:
        if 'permission changed' not in str(exc):
            raise
    else:
        raise ValueError('Changed permission accepted')
    proof = {'format': 'c111331-other-device-branch-cpu-v1',
             'passed': True, 'conditions': results,
             'changed_permission_rejected': True,
             'device_identity': 'placeholder other device under NRS 484B.283',
             'device_authority_native_verified': False,
             'original_native_observed': False,
             'legal_outcome_claimed': False}
    output = assignment/'exception-source-proof.json'
    output.write_text(json.dumps(proof, indent=2)+'\n')
    print(json.dumps({'passed': True,
                      'entry_frames': results['exception_absent']['highway_frames'],
                      'proof_sha256': sha(output)}))


if __name__ == '__main__':
    main()
