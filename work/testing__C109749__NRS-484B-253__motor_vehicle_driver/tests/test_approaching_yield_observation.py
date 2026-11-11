import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from approaching_yield_observation import observe


def materialize(root, change=None):
    files = json.loads((ROOT / 'cases/approaching_yield/diagnostic.json').read_text())['files']
    for name in ('intersection_geometry.json', 'video_frames.jsonl'):
        (root / name).write_text(files[name])
    rows = [json.loads(line) for line in files['interaction_history.jsonl'].splitlines() if line]
    if change:
        change(rows)
    (root / 'interaction_history.jsonl').write_text(
        ''.join(json.dumps(row) + '\n' for row in rows))


class ApproachingYieldObservationTests(unittest.TestCase):
    def test_sourced_outside_approach_yield_entry_clearance_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            materialize(root)
            observed = observe(root)
            self.assertEqual(observed['opposing_entry_frame'], 38036)
            self.assertEqual(observed['opposing_clearance_frame'], 38038)
            self.assertEqual(observed['ego_turn_start_frame'], 38039)
            self.assertEqual(observed['approaching_yield_samples'][0]['frame'], 38035)
            self.assertGreater(observed['approaching_yield_samples'][0]['closing_speed_mps'], 0.5)
            self.assertFalse(observed['legal_verdict_asserted'])

    def test_rejects_missing_signal_and_nonclosing_approach(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            materialize(root, lambda rows: rows[2].update(ego_left_indicator=False))
            with self.assertRaisesRegex(ValueError, 'Sourced approaching-yield sequence incomplete'):
                observe(root)
            materialize(root, lambda rows: rows[2]['oncoming'].update(velocity_xy_mps=[0, 0]))
            with self.assertRaisesRegex(ValueError, 'Sourced approaching-yield sequence incomplete'):
                observe(root)


if __name__ == '__main__':
    unittest.main()
