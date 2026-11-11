import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from yield_controller import apply_speed_control, body_in_crossing, right_hand_hold


class YieldControllerTests(unittest.TestCase):
    def test_hold_until_right_hand_body_has_entered_and_cleared(self):
        held, entered = right_hand_hold(False, False)
        self.assertTrue(held)
        held, entered = right_hand_hold(True, entered)
        self.assertTrue(held)
        held, entered = right_hand_hold(False, entered)
        self.assertFalse(held)
        self.assertTrue(entered)

    def test_native_body_and_feedback_control(self):
        polygon = [[0,0],[10,0],[10,10],[0,10]]
        def actor(x):
            points=[NS(x=x-1,y=4),NS(x=x+1,y=4),
                    NS(x=x+1,y=6),NS(x=x-1,y=6)]
            return NS(bounding_box=NS(get_world_vertices=lambda transform:points),
                      get_transform=lambda:object())
        self.assertFalse(body_in_crossing(actor(-4),polygon))
        self.assertTrue(body_in_crossing(actor(5),polygon))
        commands=[]
        vehicle=NS(get_velocity=lambda:NS(x=3.0,y=0.0,z=0.0),
                   apply_control=lambda control:commands.append(control))
        carla=NS(VehicleControl=lambda:NS())
        held=apply_speed_control(carla,vehicle,4.0,True)
        self.assertEqual(held['brake'],1.0)
        self.assertEqual(held['throttle'],0.0)
        moving=apply_speed_control(carla,vehicle,4.0,False)
        self.assertGreater(moving['throttle'],0)
        self.assertEqual(len(commands),2)


if __name__=='__main__':
    unittest.main()
