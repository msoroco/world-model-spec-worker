"""CPU physical-check triad from source-shaped diagnostic rows."""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

from physical_check import assess, motion
from prove_designated_stop import packet


def main():
    with tempfile.TemporaryDirectory(prefix='c229954-physical-', dir='.runtime-work') as temp:
        original = packet(Path(temp) / 'original', True)
        for index, row in enumerate(original['rows']):
            row['position_m'] = [5 + min(index, 100) * 0.05, 0, 0]
        path = Path(original['sources']['native_trace']['path'])
        import hashlib
        path.write_text(json.dumps(original['rows'], separators=(',', ':')) + '\n')
        original['sources']['native_trace']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        positive = assess(original)
        assert positive['status'] == 'met'
        assert positive['observation']['sampled_path_m'] >= 5
        negatives = {}
        no_progress = copy.deepcopy(original['rows'])
        for row in no_progress:
            row['position_m'] = [5, 0, 0]
        negatives['no_approach'] = motion(no_progress)
        assert not negatives['no_approach']['approach_observed']
        no_rest = copy.deepcopy(original['rows'])
        for row in no_rest:
            row['observed_speed_mps'] = 1.0
        negatives['no_rest'] = motion(no_rest)
        assert not negatives['no_rest']['rest_observed']
        missing = copy.deepcopy(original['rows'])
        missing[200].pop('position_m')
        try:
            motion(missing)
        except ValueError as error:
            assert 'position missing' in str(error)
            negatives['missing_position'] = str(error)
        else:
            raise AssertionError('Missing original position passed')
        invalid = copy.deepcopy(original)
        invalid['sources'].pop('designation')
        try:
            assess(invalid)
        except ValueError as error:
            assert 'original source reference' in str(error)
            negatives['missing_designation'] = str(error)
        else:
            raise AssertionError('Missing original designation passed')
        print(json.dumps({'format': 'worker-designated-stop-physical-cpu-proof',
                          'positive': positive, 'negative_rejections': negatives,
                          'synthetic_only': True}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
