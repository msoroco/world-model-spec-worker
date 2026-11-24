"""Exercise saved diagonal timing measurement on two synthetic controls."""
import copy
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from diagonal import DEVICE, measure, synthetic_rows


def write_rows(path, data):
    path.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in data))


def reject(source_path, context_path, expected):
    try:
        measure(source_path, context_path)
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError('Unexpected diagonal negative: ' + str(error))
        return str(error)
    raise AssertionError('Diagonal negative passed')


def main():
    folder = HERE / 'diagnostic-diagonal'
    folder.mkdir(exist_ok=True)
    context = {'source_kind': 'synthetic_scene_request', 'device_id': DEVICE,
               'governs_diagonal_movement': True,
               'official_device_original_review': 'pending',
               'statutory_exception_review': 'pending'}
    context_path = folder / 'context.json'
    context_path.write_text(json.dumps(context, indent=2) + '\n')
    positives = []
    rows_by_case = {}
    for case in ('controlled_1', 'controlled_2'):
        rows = synthetic_rows(case)
        rows_by_case[case] = rows
        path = folder / (case + '.jsonl')
        write_rows(path, rows)
        positives.append({'case': case, 'measurement': measure(path, context_path)})
    a, b = (rows_by_case[case] for case in ('controlled_1', 'controlled_2'))
    changed = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
    if changed != list(range(100, 160)) or any(
        {k: v for k, v in a[i].items() if k != 'device_state'} !=
        {k: v for k, v in b[i].items() if k != 'device_state'} for i in changed
    ):
        raise AssertionError('Controlled comparison changed path or other source field')
    if [p['measurement']['denied_during_crossing_frames'] for p in positives] != [0, 60]:
        raise AssertionError('Diagonal device-state contrast differs')
    if [p['measurement']['first_entry_device_state'] for p in positives] != [
        'diagonal_walk', 'diagonal_dont_walk'
    ]:
        raise AssertionError('First-entry device distinction differs')
    negative_path = folder / 'negative.jsonl'
    negatives = {}
    variants = {
        'missing_frame': (lambda values: values.pop(), '600-frame'),
        'off_diagonal': (lambda values: values[200]['pedestrian_xy_m'].__setitem__(1, 1.0), 'footprint/position'),
        'wrong_governing_device': (lambda values: values[200].__setitem__('device_id', 'other'), 'identity'),
        'missing_full_body': (lambda values: values[200].__setitem__('footprint_xy_m', []), 'footprint'),
    }
    for name, (mutate, expected) in variants.items():
        values = copy.deepcopy(b)
        mutate(values)
        write_rows(negative_path, values)
        negatives[name] = reject(negative_path, context_path, expected)
    negative_path.unlink()
    bad_context = {**context, 'governs_diagonal_movement': False}
    bad_context_path = folder / 'negative-context.json'
    bad_context_path.write_text(json.dumps(bad_context) + '\n')
    negatives['non_governing_context'] = reject(folder / 'controlled_2.jsonl', bad_context_path, 'governance')
    bad_context_path.unlink()
    proof = {'format': 'c109166-diagonal-source-proof-v1',
             'positive': positives, 'changed_device_state_frames': changed,
             'rejected_negatives': negatives, 'selected': False,
             'native_executed': False, 'original_pixels_reviewed': False,
             'legal_verdict_claimed': False}
    path = HERE / 'diagonal-source-proof.json'
    path.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'positive_cases': 2, 'controlled_changed_frames': len(changed),
                      'negative_rejections': len(negatives), 'native_executed': False}))


if __name__ == '__main__':
    main()
