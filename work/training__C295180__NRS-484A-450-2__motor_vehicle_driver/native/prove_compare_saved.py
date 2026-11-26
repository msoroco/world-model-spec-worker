"""CPU positive and negative checks for the independent stop comparison."""
import json
import tempfile
from pathlib import Path

from compare_saved import audit
from prove_saved_stop_line import SCRATCH, build, seal, write_json


def reject(a, b, expected):
    try:
        audit(a, b)
    except ValueError as error:
        if str(error) != expected:
            raise
        return str(error)
    raise AssertionError('Invalid comparison accepted')


def prove():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
        root = Path(temporary)
        a, b = root / 'a', root / 'b'
        a.mkdir()
        b.mkdir()
        build(a, 'full_stop')
        case_b = build(b, 'rolling')
        positive = audit(a, b)
        fixed = json.loads((b / 'stop_reference.json').read_text())
        fixed['paint_color'] = 'changed'
        write_json(b / 'stop_reference.json', fixed)
        seal(b, case_b)
        negatives = {'changed_reference': reject(
            a, b, 'Fixed stop sign, line or intersection source differs')}
        fixed.pop('paint_color')
        write_json(b / 'stop_reference.json', fixed)
        seal(b, case_b)
        native = [json.loads(line) for line in (a / 'native_samples.jsonl').read_text().splitlines()]
        for row in native:
            row['case_id'] = case_b
        (b / 'native_samples.jsonl').write_text(''.join(
            json.dumps(row, sort_keys=True) + '\n' for row in native))
        seal(b, case_b)
        negatives['missing_difference'] = reject(
            a, b, 'Controlled stop diagnostic difference absent')
        return {'format': 'c295180-independent-comparison-cpu-proof-v1',
                'positive': positive, 'negative_rejections': negatives,
                'physical_completion_claimed': False}


if __name__ == '__main__':
    print(json.dumps(prove(), indent=2, sort_keys=True))
