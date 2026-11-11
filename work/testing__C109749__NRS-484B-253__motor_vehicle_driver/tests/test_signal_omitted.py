import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from signal_omitted_observation import observe


def fixture(root, change=None):
    files = json.loads((ROOT / 'cases/signal_omitted/diagnostic.json').read_text())['files']
    for name in ('intersection_geometry.json', 'video_frames.jsonl'):
        (root / name).write_text(files[name])
    rows = [json.loads(line) for line in files['interaction_history.jsonl'].splitlines() if line]
    if change:
        change(rows)
    (root / 'interaction_history.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))


class SignalOmittedObservationTests(unittest.TestCase):
    def test_yield_then_turn_with_no_indicator_readback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root)
            measured = observe(root)
            self.assertEqual(measured['subject_yield_frames'], [38035])
            self.assertEqual(measured['ego_left_indicator_frames'], [])
            self.assertLess(measured['initial_oncoming_clearance_frame'], measured['ego_turn_start_frame'])
            self.assertFalse(measured['legal_verdict_asserted'])

    def test_rejects_any_left_indicator_readback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture(root, lambda rows: rows[1].update(ego_left_indicator=True))
            with self.assertRaisesRegex(ValueError, 'observed left indicator'):
                observe(root)


if __name__ == '__main__':
    unittest.main()
