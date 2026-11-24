"""Original-footprint-driven controller behavior without CARLA."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from controlled_yielding import Controller

CROSSING = [[-2,-2],[2,-2],[2,2],[-2,2]]
OUTSIDE = [[-5,-1],[-4,-1],[-4,1],[-5,1]]
INSIDE = [[-1,-1],[1,-1],[1,1],[-1,1]]
AFTER = [[4,-1],[5,-1],[5,1],[4,1]]


class ControllerTests(unittest.TestCase):
    def test_yield_policy_waits_for_original_other_exit(self):
        controller=Controller('wait_for_other_clear',CROSSING,1,1)
        self.assertEqual(controller.controls(1.2)['ego']['brake'],1)
        controller.update_other(OUTSIDE)
        self.assertEqual(controller.controls(1.2)['ego']['brake'],1)
        controller.update_other(INSIDE)
        self.assertEqual(controller.controls(1.2)['ego']['brake'],1)
        controller.update_other(AFTER)
        self.assertEqual(controller.controls(1.2)['ego']['throttle'],.35)
        self.assertTrue(controller.other_cleared)

    def test_advance_policy_moves_at_release_before_other_clear(self):
        controller=Controller('advance_at_release',CROSSING,1,1)
        controller.update_other(INSIDE)
        self.assertEqual(controller.controls(1.2)['ego']['throttle'],.35)
        self.assertFalse(controller.other_cleared)
        with self.assertRaisesRegex(ValueError,'unknown'):
            Controller('invented',CROSSING,1,1)


if __name__=='__main__':
    unittest.main()
