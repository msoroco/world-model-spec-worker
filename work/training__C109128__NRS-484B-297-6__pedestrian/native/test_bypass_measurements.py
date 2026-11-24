"""Positive and negative checks of source-derived bypass measurements."""
import copy
import json
import tempfile
from pathlib import Path

from prove_bypass_measurements import HERE, CONTEXT, derive, digest


def main():
    source = HERE / 'diagnostic-bypass/condition_a.jsonl'
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    original = derive(source)
    scratch = HERE.parents[1] / '.runtime-work' / 'c109128-measurement-tests'
    scratch.mkdir(parents=True, exist_ok=True)
    rejected = []
    def prevent_return(items):
        for index in range(370, 600):
            items[index]['pedestrian_xy_m'][1] = 1.55
            for foot_index, point in enumerate(items[index]['footprint_xy_m']):
                point[1] = 1.39 if foot_index in (0, 2) else 1.71

    def teleport(items):
        items[220]['pedestrian_xy_m'][0] = 80.0
        for foot_index, point in enumerate(items[220]['footprint_xy_m']):
            point[0] = 79.84 if foot_index in (0, 1) else 80.16

    with tempfile.TemporaryDirectory(dir=scratch) as directory:
        target = Path(directory) / 'source.jsonl'
        for name, mutate, expected in (
            ('missing_frame', lambda r: r.pop(), 'Expected 600 source frames'),
            ('frame_swap', lambda r: r.__setitem__(slice(220, 222), list(reversed(r[220:222]))), 'Invalid bypass source row'),
            ('nonfinite_center', lambda r: r[220]['pedestrian_xy_m'].__setitem__(0, float('inf')), 'Nonfinite bypass geometry'),
            ('teleport', teleport, 'Pedestrian frame discontinuity'),
            ('no_return', prevent_return, 'Missing complete sidewalk bypass and return'),
        ):
            altered = copy.deepcopy(rows)
            mutate(altered)
            target.write_text(''.join(json.dumps(row) + '\n' for row in altered))
            try:
                derive(target)
            except ValueError as error:
                if str(error) != expected:
                    raise AssertionError(f'{name}: expected {expected}, got {error}') from error
                rejected.append({'mutation': name, 'rejection': str(error)})
            else:
                raise AssertionError(f'{name}: accepted damaged source')
        bad_context = Path(directory) / 'context.json'
        context = json.loads(CONTEXT.read_text())
        context['physical_obstruction_verified'] = True
        bad_context.write_text(json.dumps(context))
        try:
            derive(source, bad_context)
        except ValueError as error:
            if str(error) != 'Untrusted bypass context':
                raise
            rejected.append({'mutation': 'fake_physical_authority', 'rejection': str(error)})
        else:
            raise AssertionError('Accepted false physical authority')
    receipt = {'format': 'c109128-measurement-negative-proof-v1',
               'passed': len(rejected) == 6,
               'source_sha256': digest(source), 'context_sha256': digest(CONTEXT),
               'positive': original, 'negative_rejections': rejected,
               'physical_success_claimed': False, 'legal_verdict_claimed': False}
    target = HERE / 'bypass-measurement-negative-proof.json'
    target.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': receipt['passed'], 'negative_count': len(rejected),
                      'proof_sha256': digest(target)}))


if __name__ == '__main__':
    main()
