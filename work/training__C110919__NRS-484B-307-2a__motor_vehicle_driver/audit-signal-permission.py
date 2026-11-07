"""Independent saved-source positive and negative proof for right-turn permission."""
import copy
import hashlib
import json
import tempfile
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
import measure


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    proof = {}
    for case in ('controlled_1', 'controlled_2'):
        source = HERE / 'native' / 'fixtures' / (case + '-480.json')
        rows = json.loads(source.read_text())
        assert rows['source_kind'] == 'synthetic_cpu'
        assert len(rows['frames']) == 480
        positive = measure.measure(source, digest(source))
        assert positive['circular_green_frames'] == 480
        assert positive['turn_prohibition_absent'] is True
        assert positive['right_turn_permission_context_observed_in_source'] is True
        assert positive['physical_behavior_observed'] is False
        assert positive['legal_verdict'] is None
        assert all(row['signal_state'] == 'circular_green' and
                   row['signal_governs_ego'] is True and
                   row['turn_prohibition_present'] is False for row in rows['frames'])
        rejected = []
        for field, value in (('signal_state', 'red'),
                             ('signal_governs_ego', False),
                             ('turn_prohibition_present', True)):
            altered = copy.deepcopy(rows)
            altered['frames'][positive['turn_entry_frame']][field] = value
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'source.json'
                path.write_text(json.dumps(altered, separators=(',', ':')) + '\n')
                try:
                    measure.measure(path, digest(path))
                except ValueError:
                    rejected.append(field)
                else:
                    raise AssertionError('Saved measurement accepted altered ' + field)
        assert len(rejected) == 3
        proof[case] = {'source_sha256': digest(source),
                       'turn_entry_frame': positive['turn_entry_frame'],
                       'green_frames': 480, 'mutation_rejections': rejected}
    return {'format': 'c110919-signal-permission-cpu-proof-v1',
            'passed': True, 'source_kind': 'synthetic_cpu',
            'physical_or_legal_acceptance': False, 'cases': proof}


if __name__ == '__main__':
    receipt = audit()
    (HERE / 'signal-permission-proof.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True))
