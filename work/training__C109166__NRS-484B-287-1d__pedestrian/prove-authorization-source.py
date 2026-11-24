"""Retain and test the exact diagonal-authorization synthetic source pair."""
import copy
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from authorization import DEVICE, measure, requested, sha


def put(path, rows):
    Path(path).write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n'
                                  for row in rows))


def reject(source, context):
    try:
        measure(source, context)
    except ValueError as error:
        return str(error)
    raise AssertionError('Malformed diagonal source accepted')


def main():
    folder = HERE / 'diagnostic-authorization'
    folder.mkdir(exist_ok=True)
    context = {'source_kind': 'synthetic_scene_request', 'device_id': DEVICE,
               'official_device_verified': False,
               'exception_484b290_reviewed': False,
               'original_device_pixels_reviewed': False}
    context_path = folder / 'context.json'
    context_path.write_text(json.dumps(context, indent=2) + '\n')
    records = []
    rows_by_case = []
    for case in ('probe_01', 'probe_02'):
        rows = requested(case)
        rows_by_case.append(rows)
        path = folder / (case + '.jsonl')
        put(path, rows)
        measurement = measure(path, context_path)
        records.append({'case': case, 'measurement': measurement,
                        'source_sha256': sha(path)})
    left, right = rows_by_case
    changed = [i for i, (a, b) in enumerate(zip(left, right)) if a != b]
    if changed != list(range(600)) or any(
        {k: v for k, v in a.items() if k != 'requested_diagonal_authorization'} !=
        {k: v for k, v in b.items() if k != 'requested_diagonal_authorization'}
        for a, b in zip(left, right)
    ):
        raise AssertionError('Controlled pair changed route or another field')
    if [r['measurement']['requested_authorization_at_entry'] for r in records] != [True, False]:
        raise AssertionError('Diagonal first-entry authorization contrast absent')
    bad = folder / 'negative.jsonl'
    negatives = []
    for name, change in (
        ('missing_frame', lambda rows: rows.pop()),
        ('missing_footprint', lambda rows: rows[120].__setitem__('footprint_xy_m', [])),
        ('off_diagonal', lambda rows: rows[120]['pedestrian_xy_m'].__setitem__(1, 4)),
        ('wrong_device', lambda rows: rows[120].__setitem__('device_id', 'other')),
        ('fake_official_authority', lambda rows: rows[120].__setitem__('official_device_verified', True)),
        ('mixed_authorization', lambda rows: rows[120].__setitem__('requested_diagonal_authorization', True)),
    ):
        variant = copy.deepcopy(right)
        change(variant)
        put(bad, variant)
        negatives.append({'mutation': name, 'error': reject(bad, context_path)})
    bad.unlink()
    bad_context = folder / 'bad-context.json'
    bad_context.write_text(json.dumps(dict(context, official_device_verified=True)) + '\n')
    negatives.append({'mutation': 'fake_context_authority',
                      'error': reject(folder / 'probe_02.jsonl', bad_context)})
    bad_context.unlink()
    receipt = {'format': 'c109166-1d-source-proof-v1', 'frames': 600,
               'rate_hz': 20, 'controlled_variable': 'requested_diagonal_authorization',
               'records': records, 'changed_frames': len(changed),
               'negative_rejections': negatives,
               'physical_success_claimed': False, 'legal_verdict_claimed': False,
               'passed': len(negatives) == 7}
    target = HERE / 'authorization-source-proof.json'
    target.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': receipt['passed'], 'receipt_sha256': sha(target),
                      'positives': len(records), 'negatives': len(negatives)}))


if __name__ == '__main__':
    main()
