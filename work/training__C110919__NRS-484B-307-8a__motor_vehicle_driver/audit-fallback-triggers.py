"""Independent CPU decision-boundary checks for the three red-turn fallbacks.

These deliberately authored metric records exercise the selection logic. They
are not observations of a Native run or decoded original camera pixels.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('red_turn_engineering', HERE/'native'/'engineering.py')
engineering = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(engineering)


def run() -> dict:
    cases = []
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)/'trigger-metrics.json'

        def decision(candidate: str, metric: str, value: float, kind='original_native_and_video') -> bool:
            record = {'source_kind': kind, metric: value}
            path.write_text(json.dumps(record, allow_nan=True))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            return engineering.evaluate_trigger(candidate, record, path, digest)

        for candidate, trigger in engineering.TRIGGERS.items():
            name = trigger['metric']
            threshold = trigger['threshold']
            delta = 0.01
            high = decision(candidate, name, threshold+delta)
            equal = decision(candidate, name, threshold)
            low = decision(candidate, name, threshold-delta)
            expected = (True, False, False) if trigger['op']=='>' else (False, False, True)
            assert (high, equal, low) == expected, candidate
            cases.append({'candidate': candidate, 'metric': name, 'threshold': threshold,
                          'higher': high, 'equal': equal, 'lower': low})

            for invalid in (float('nan'), float('inf'), -float('inf'), True):
                try:
                    decision(candidate, name, invalid)
                except ValueError as exc:
                    assert 'metric' in str(exc) or 'bound to original' in str(exc)
                else:
                    raise AssertionError(f'{candidate} accepted nonfinite/non-numeric metric')
            try:
                decision(candidate, name, threshold+delta, 'synthetic_cpu')
            except ValueError as exc:
                assert 'original Native and video' in str(exc)
            else:
                raise AssertionError(f'{candidate} accepted a synthetic source as original')

            record = {'source_kind': 'original_native_and_video', name: threshold+delta}
            path.write_text(json.dumps(record))
            try:
                engineering.evaluate_trigger(candidate, record, path, '0'*64)
            except ValueError as exc:
                assert 'hash' in str(exc)
            else:
                raise AssertionError(f'{candidate} accepted an altered source digest')

    return {'passed': True, 'assignment_id': HERE.name, 'decisions': cases,
            'negative_checks_per_fallback': ['nan', 'positive_infinity', 'negative_infinity',
                                             'boolean', 'synthetic_source', 'wrong_hash'],
            'scope': 'authored CPU metric decision proof only; no physical trigger observation'}


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
