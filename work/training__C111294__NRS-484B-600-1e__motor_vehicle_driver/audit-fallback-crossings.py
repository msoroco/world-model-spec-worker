"""Independently remeasure every saved speed fallback crossing and source hash."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE/'native'))
import engineering
import geometry
import measure_speed

CASES = ('below_80_mph', 'inside_80_mph', 'above_80_mph')
VARIANTS = ('baseline', 'fallback1', 'fallback2', 'fallback3')


def main():
    proof = json.loads((HERE/'fallback-crossings-proof.json').read_text())
    if (proof['passed'] is not True or proof['selected'] is not False or
        proof['native_executed'] is not False or len(proof['rows']) != 12):
        raise AssertionError('Synthetic proof inventory differs')
    seen = set()
    for entry in proof['rows']:
        case, variant = entry['case'], entry['variant']
        if case not in CASES or variant not in VARIANTS or (case, variant) in seen:
            raise AssertionError('Case or variant inventory differs')
        seen.add((case, variant))
        path = HERE/'draft-fixtures/fallback-crossings'/f'{case}-{variant}.jsonl'
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != entry['source_sha256']:
            raise AssertionError('Synthetic source changed')
        rows = [json.loads(line) for line in raw.splitlines()]
        if len(rows) != measure_speed.FRAMES or any(row['source_kind'] != 'synthetic_cpu_fixture' for row in rows):
            raise AssertionError('Source inventory or kind differs')
        baseline_mph = geometry.SPEED_MPH[case]
        expected_mph = baseline_mph + (-1 if variant == 'fallback1' else
                                       1 if variant == 'fallback3' else 0)
        expected_speed = expected_mph/measure_speed.MPS_TO_MPH
        expected_x = 2.25 if variant == 'fallback2' else 1.75
        for index, row in enumerate(rows):
            if (row['frame'] != index or row['ego_position_m'] != [expected_x, -70+expected_speed*index/20, 0] or
                row['ego_velocity_mps'] != [0, expected_speed, 0]):
                raise AssertionError('Crossing altered another Native field')
        metrics = engineering.measured_gates(case, path, digest)
        if metrics != entry['metrics']:
            raise AssertionError('Measured metrics differ')
        decisions = {name: engineering.evaluate(case, name, path, digest)['triggered']
                     for name in VARIANTS[1:]}
        if decisions != entry['decisions'] or decisions != {name: name == variant for name in VARIANTS[1:]}:
            raise AssertionError('Threshold decision differs')
    if seen != {(case, variant) for case in CASES for variant in VARIANTS}:
        raise AssertionError('Missing case/variant crossing')
    print(json.dumps({'passed': True, 'source_hashed_synthetic_crossings': 12,
                      'cases': 3, 'distinct_fallback_triggers_per_case': 3,
                      'selected': False, 'original_native_observed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
