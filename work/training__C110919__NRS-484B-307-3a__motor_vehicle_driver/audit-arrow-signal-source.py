"""Replay the saved arrow and opposing-red source, including altered-source negatives."""
import copy
import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
import measure


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cases = {}
    for suffix in ('witness_1', 'witness_2'):
        source = HERE / 'native/fixtures' / (suffix + '-480.json')
        data = json.loads(source.read_text())
        frames = data['frames']
        assert data['source_kind'] == 'synthetic_cpu' and len(frames) == 480
        measured = measure.measure(source, sha(source))
        entry = measured['turn_entry_frame']
        assert measured['circular_green_with_right_arrow_frames'] == 480
        assert measured['opposing_steady_red_frames'] == 480
        assert measured['physical_behavior_observed'] is False
        assert measured['legal_verdict'] is None
        assert 0 <= entry < 480
        rejected = []
        for field, value in (
            ('signal_state', 'circular_green'),
            ('signal_governs_ego', False),
            ('right_turn_arrow_state', 'off'),
            ('arrow_governs_right_turn', False),
            ('opposing_signal_state', 'green'),
        ):
            altered = copy.deepcopy(data)
            altered['frames'][entry][field] = value
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'altered.json'
                path.write_text(json.dumps(altered, separators=(',', ':')) + '\n')
                try:
                    measure.measure(path, sha(path))
                except ValueError:
                    rejected.append(field)
                else:
                    raise AssertionError('altered source accepted: ' + field)
        assert len(rejected) == 5
        cases[suffix] = {'source_sha256': sha(source), 'turn_entry_frame': entry,
                         'positive_frames': 480, 'rejected_mutations': rejected}
    receipt = {'format': 'c110919-arrow-signal-source-proof-v1', 'passed': True,
               'source_kind': 'synthetic_cpu', 'cases': cases,
               'original_native_or_pixel_observation': False, 'legal_verdict': None}
    (HERE / 'arrow-signal-source-proof.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
