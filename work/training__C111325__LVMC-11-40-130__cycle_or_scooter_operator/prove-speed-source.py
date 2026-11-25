"""Exercise two full-duration synthetic bicycle approach requests."""
import copy
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from speed import measure, requested, sha


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))


def rejected(path, context):
    try:
        measure(path, context)
    except ValueError as error:
        return str(error)
    raise AssertionError('Damaged speed source accepted')


def main():
    folder = HERE / 'diagnostic-speed'
    folder.mkdir(exist_ok=True)
    context = {'context_id': 'c111325-stop-approach-v1',
               'cell_id': 'C111325', 'control': 'stop_sign',
               'actor_requested': 'bicycle', 'stop_line_x_m': 0.0,
               'visibility_m': 75.0, 'wet_road': False,
               'crossing_pedestrian_present': False,
               'physical_conditions_verified': False,
               'original_native_observed': False}
    context_path = folder / 'context.json'
    context_path.write_text(json.dumps(context, indent=2) + '\n')
    records = []
    sources = []
    for condition in ('condition_a', 'condition_b'):
        rows = requested(condition)
        path = folder / (condition + '.jsonl')
        write_rows(path, rows)
        records.append(measure(path, context_path))
        sources.append(rows)
    a, b = sources
    fixed = set(a[0]) - {'bicycle_center_xy_m', 'requested_speed_condition'}
    if any({k: left[k] for k in fixed} != {k: right[k] for k in fixed}
           for left, right in zip(a, b)):
        raise AssertionError('Speed comparison changed fixed context')
    if not records[0]['peak_position_derived_speed_mps'] < records[1]['peak_position_derived_speed_mps']:
        raise AssertionError('Speed contrast absent')
    negatives = []
    scratch = HERE.parents[1] / '.runtime-work/c111325'
    scratch.mkdir(parents=True, exist_ok=True)
    temporary = scratch / 'speed-negative.jsonl'
    for name, mutate in (
        ('missing_frame', lambda rows: rows.pop()),
        ('wrong_stop_line', lambda rows: rows[200].__setitem__('stop_line_x_m', 1.0)),
        ('teleport', lambda rows: rows[200]['bicycle_center_xy_m'].__setitem__(0, 10.0)),
        ('mixed_condition', lambda rows: rows[200].__setitem__('requested_speed_condition', 'condition_b')),
        ('reverse_motion', lambda rows: rows[200]['bicycle_center_xy_m'].__setitem__(0, -80.0)),
    ):
        rows = copy.deepcopy(a)
        mutate(rows)
        write_rows(temporary, rows)
        negatives.append({'mutation': name, 'rejection': rejected(temporary, context_path)})
    temporary.unlink()
    false_context = scratch / 'speed-false-context.json'
    false_context.write_text(json.dumps(dict(context, physical_conditions_verified=True)) + '\n')
    negatives.append({'mutation': 'false_physical_authority',
                      'rejection': rejected(folder / 'condition_a.jsonl', false_context)})
    false_context.unlink()
    proof = {'format': 'c111325-speed-source-proof-v1',
             'passed': True, 'frames_per_condition': 600, 'rate_hz': 20,
             'controlled_variable': 'bicycle_approach_speed',
             'records': records, 'negative_rejections': negatives,
             'original_native_observed': False,
             'prudence_verdict_claimed': False}
    target = HERE / 'speed-source-proof.json'
    target.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'passed': True, 'proof_sha256': sha(target),
                      'peak_speeds_mps': [r['peak_position_derived_speed_mps'] for r in records],
                      'negative_count': len(negatives)}))


if __name__ == '__main__':
    main()
