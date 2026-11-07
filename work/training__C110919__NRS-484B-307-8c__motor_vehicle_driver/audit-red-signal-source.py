"""Replay exact saved red-signal sources with independent altered-source negatives."""
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
    for suffix in ('probe_a', 'probe_b'):
        source = HERE / 'native/fixtures' / (suffix + '-480.json')
        data = json.loads(source.read_text())
        assert data['source_kind'] == 'synthetic_cpu' and len(data['frames']) == 480
        result = measure.measure(source, sha(source))
        assert result['steady_red_frames'] == 480
        assert result['physical_behavior_observed'] is False and result['legal_verdict'] is None
        entry = result['turn_entry_frame']
        assert 0 <= entry < 480
        rejected = []
        for field, value in (('signal_state', 'green'), ('signal_governs_ego', False),
                             ('approach_lane', 'left'), ('intersecting_road', 'one_way')):
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
        assert len(rejected) == 4
        cases[suffix] = {'source_sha256': sha(source), 'turn_entry_frame': entry,
                         'positive_frames': 480, 'rejected_mutations': rejected}
    receipt = {'format': 'c110919-red-signal-source-proof-v1', 'passed': True,
               'source_kind': 'synthetic_cpu', 'cases': cases,
               'original_native_or_pixel_observation': False, 'legal_verdict': None}
    (HERE / 'red-signal-source-proof.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
