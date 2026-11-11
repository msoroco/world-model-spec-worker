import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from approaching_no_yield_controller import ProceedBeforeClearanceController
from approaching_no_yield_observation import observe


def source_fixture(root, change=None):
    files = json.loads((ROOT / 'cases/approaching_no_yield/diagnostic.json').read_text())['files']
    for name in ('intersection_geometry.json', 'video_frames.jsonl'):
        (root / name).write_text(files[name])
    rows = [json.loads(line) for line in files['interaction_history.jsonl'].splitlines() if line]
    if change:
        change(rows)
    (root / 'interaction_history.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))


class ApproachingNoYieldTests(unittest.TestCase):
    def test_proceed_policy_turns_with_opponent_still_approaching(self):
        control = ProceedBeforeClearanceController(turn_distance_m=4.0)
        output = control.step(distance_to_hold_m=3.0, ego_speed_mps=3.0,
                              oncoming_distance_to_conflict_m=9.0,
                              oncoming_closing_speed_mps=5.0,
                              oncoming_in_intersection=False, oncoming_cleared=False,
                              turn_complete=False)
        self.assertEqual(output['state'], 'turn')
        self.assertTrue(output['left_indicator'])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_fixture(root)
            measured = observe(root)
            self.assertLess(measured['ego_turn_start_frame'], measured['opposing_entry_frame'])
            self.assertFalse(measured['legal_verdict_asserted'])

    def test_rejects_nonclosing_opponent_at_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_fixture(root, lambda rows: rows[2]['oncoming'].update(velocity_xy_mps=[0, 0]))
            with self.assertRaisesRegex(ValueError, 'No sourced signalled turn'):
                observe(root)


if __name__ == '__main__':
    unittest.main()
