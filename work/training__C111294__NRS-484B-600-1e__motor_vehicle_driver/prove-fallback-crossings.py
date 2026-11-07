"""Save source-bound synthetic threshold crossings for each speed case."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE/'native'))
import engineering
import geometry
import measure_speed

OUT = HERE/'draft-fixtures/fallback-crossings'
CASES = ('below_80_mph', 'inside_80_mph', 'above_80_mph')
VARIANTS = ('baseline', 'fallback1', 'fallback2', 'fallback3')


def source(case, variant):
    target = geometry.SPEED_MPH[case]
    speed = target + (-1.0 if variant == 'fallback1' else
                      1.0 if variant == 'fallback3' else 0.0)
    rows = [json.loads(line) for line in measure_speed.synthetic_fixture(speed).splitlines()]
    if variant == 'fallback2':
        for row in rows:
            row['ego_position_m'][0] += 0.5
    return ''.join(json.dumps(row, sort_keys=True)+'\n' for row in rows).encode()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for case in CASES:
        for variant in VARIANTS:
            path = OUT/f'{case}-{variant}.jsonl'
            raw = source(case, variant)
            path.write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            metrics = engineering.measured_gates(case, path, digest)
            decisions = {name: engineering.evaluate(case, name, path, digest)['triggered']
                         for name in VARIANTS[1:]}
            expected = {name: name == variant for name in VARIANTS[1:]}
            if decisions != expected or metrics['source_kind'] != 'synthetic_cpu_fixture':
                raise AssertionError(f'Crossing differs: {case} {variant} {decisions}')
            results.append({'case': case, 'variant': variant, 'source_sha256': digest,
                            'metrics': metrics, 'decisions': decisions})
    proof = {'passed': True, 'source_kind': 'synthetic_cpu_fixture',
             'selected': False, 'native_executed': False,
             'cases': len(CASES), 'crossings': len(results), 'rows': results}
    (HERE/'fallback-crossings-proof.json').write_text(json.dumps(proof, indent=2)+'\n')
    print(json.dumps({'passed': True, 'cases': len(CASES), 'crossings': len(results)}))


if __name__ == '__main__':
    main()
