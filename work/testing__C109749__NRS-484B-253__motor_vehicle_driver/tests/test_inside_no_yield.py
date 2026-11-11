import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from inside_no_yield_controller import ProceedBeforeClearanceController
from inside_no_yield_observation import observe


class InsideNoYieldTests(unittest.TestCase):
    def test_proceed_policy_turns_with_inside_opponent(self):
        controller = ProceedBeforeClearanceController()
        inputs = dict(distance_to_hold_m=3.0, ego_speed_mps=2.0,
                      oncoming_distance_to_conflict_m=1.0,
                      oncoming_closing_speed_mps=5.0,
                      oncoming_in_intersection=True,
                      oncoming_cleared=False, turn_complete=False)
        command = controller.step(**inputs)
        self.assertEqual(command['state'], 'turn')
        self.assertEqual(command['brake'], 0.0)
        self.assertTrue(command['left_indicator'])

    def test_original_source_order_and_negative_clearance(self):
        source = json.loads((ROOT / 'cases/inside_no_yield/diagnostic.json').read_text())['files']
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('intersection_geometry.json', 'interaction_history.jsonl',
                         'video_frames.jsonl'):
                (root / name).write_text(source[name])
            result = observe(root)
            self.assertEqual(result['moving_overlap_frames'], [38035])
            self.assertLess(result['ego_turn_start_frame'],
                            result['initial_oncoming_clearance_frame'])
            self.assertFalse(result['legal_verdict_asserted'])
            rows = [json.loads(line) for line in source['interaction_history.jsonl'].splitlines()]
            rows[2]['ego']['velocity_xy_mps'] = [0, 0]
            (root / 'interaction_history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'No sourced moving subject turn'):
                observe(root)
