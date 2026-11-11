import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent.parent
sys.path.insert(0, str(ROOT))
from signal_comparison_audit import compare


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SignalComparisonTests(unittest.TestCase):
    def test_rejects_changed_fixed_subject_trajectory(self):
        signalled = REPO / '.runtime-work/c109749-inside-yield-delivery-v2/attempt'
        omitted = REPO / '.runtime-work/c109749-signal-omitted-delivery-v1/attempt'
        with tempfile.TemporaryDirectory() as tmp:
            changed = Path(tmp)
            for name in ('capture-seal.json', 'diagnostic-audit.json',
                         'intersection_geometry.json', 'interaction_history.jsonl',
                         'video_frames.jsonl'):
                shutil.copy2(omitted / name, changed / name)
            history = changed / 'interaction_history.jsonl'
            rows = [json.loads(line) for line in history.read_text().splitlines()]
            rows[2]['ego']['position_xy_m'][0] += 1.0
            history.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            seal = json.loads((changed / 'capture-seal.json').read_text())
            seal['sources']['interaction_history.jsonl'] = sha(history)
            (changed / 'capture-seal.json').write_text(json.dumps(seal))
            audit = json.loads((changed / 'diagnostic-audit.json').read_text())
            audit['original_sources']['history_sha256'] = sha(history)
            (changed / 'diagnostic-audit.json').write_text(json.dumps(audit))
            with self.assertRaisesRegex(ValueError, 'Fixed original field differs: ego'):
                compare(signalled, changed)


if __name__ == '__main__':
    unittest.main()
