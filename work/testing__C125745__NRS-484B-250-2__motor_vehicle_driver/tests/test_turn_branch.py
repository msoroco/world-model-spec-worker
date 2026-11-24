import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from turn_branch import build_turn_pair, validate_turn_pair


class TurnBranchTests(unittest.TestCase):
    def test_opposite_turn_pair_isolates_intent_and_exit(self):
        scene = json.loads((ROOT / 'fourth-site.json').read_text())
        left, straight = build_turn_pair(scene)
        report = validate_turn_pair(left, straight)
        self.assertEqual(report['left_exit_offset_m'], 15)
        self.assertEqual(report['straight_exit_offset_m'], 0)
        self.assertEqual(straight['approaches']['other']['route_xy_m'][-1], [0, 0])
        self.assertEqual(left['approaches']['other']['route_xy_m'][:-1],
                         straight['approaches']['other']['route_xy_m'][:-1])
        changed = copy.deepcopy(straight)
        changed['other_left_turn_intended'] = True
        with self.assertRaisesRegex(ValueError, 'intent commands'):
            validate_turn_pair(left, changed)
        changed = copy.deepcopy(straight)
        changed['approaches']['other']['route_xy_m'][-1] = [15, 15]
        with self.assertRaisesRegex(ValueError, 'left and straight exits'):
            validate_turn_pair(left, changed)
        changed = copy.deepcopy(straight)
        changed['other_release_frame'] = 48
        with self.assertRaisesRegex(ValueError, 'fixed condition'):
            validate_turn_pair(left, changed)
        changed = copy.deepcopy(straight)
        changed['approaches']['other']['route_xy_m'][0] = [31, 0]
        with self.assertRaisesRegex(ValueError, 'entry path changed'):
            validate_turn_pair(left, changed)


if __name__ == '__main__':
    unittest.main()
