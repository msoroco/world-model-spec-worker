import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from three_lane_left_turn import select_left_turn_connection, preparation_distance_m
from test_three_lane_route import corridor, Lane


class LeftTurnRouteTests(unittest.TestCase):
    def route(self,direction=1,left=True):
        _,right=corridor(direction)
        centers=[waypoint.left for waypoint in right]
        for a,b in zip(centers,centers[1:]):a.successor=b
        junction=Lane(2*direction,direction*12.5,direction*3.5,direction)
        junction.is_junction=True
        centers[-1].successor=junction
        exit_lane=Lane(7,direction*12.5,direction*6,0)
        exit_lane.road_id=88
        turn=direction if left else -direction
        exit_lane.transform.get_forward_vector=lambda: NS(x=0,y=turn)
        junction.successor=exit_lane
        return right

    def test_left_exit_selected_in_both_approach_directions(self):
        for direction in (1,-1):
            selected=select_left_turn_connection(self.route(direction))
            self.assertEqual(selected['left_exit'].road_id,88)
            self.assertAlmostEqual(selected['turn_angle_deg'],90)
            self.assertTrue(selected['junction_entered'])
            self.assertGreater(preparation_distance_m((0,0),(direction*10,0),(direction,0)),0)

    def test_rejects_right_exit_and_disconnected_junction(self):
        with self.assertRaisesRegex(ValueError,'No connected'):
            select_left_turn_connection(self.route(left=False))
        route=self.route()
        route[-1].left.successor=None
        with self.assertRaisesRegex(ValueError,'No connected'):
            select_left_turn_connection(route)


if __name__=='__main__':
    unittest.main()
