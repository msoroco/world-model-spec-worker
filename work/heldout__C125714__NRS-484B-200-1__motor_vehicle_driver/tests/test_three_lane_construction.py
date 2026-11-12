import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from three_lane_construction import three_lane_neighbors,three_lane_section,select_three_lane_route


def section(x,direction=1):
    def lane(lane_id,y,heading):
        return NS(road_id=11,lane_id=lane_id,lane_width=3.5,is_junction=False,
                  transform=NS(location=NS(x=x,y=y),
                  get_forward_vector=lambda:NS(x=heading,y=0)))
    right=lane(-1*direction,3.5*direction,direction)
    center=lane(-2*direction,0,direction)
    far=lane(1*direction,-3.5*direction,-direction)
    right.get_right_lane=lambda:None
    right.get_left_lane=lambda:center
    center.get_left_lane=lambda:far
    far.get_left_lane=lambda:None
    return right,center,far


class ThreeLaneTests(unittest.TestCase):
    def test_both_directions_and_full_road_width(self):
        for direction,label in ((1,'east'),(-1,'west')):
            points=[section(i*2.5*direction,direction)[0] for i in range(14)]
            for i,point in enumerate(points):
                point.next=lambda step,i=i:[points[i+1]] if i+1<len(points) else []
            world=NS(get_spawn_points=lambda:[NS(location=NS(x=0,y=3.5*direction))],
                     get_waypoint=lambda _:points[0])
            self.assertEqual(select_three_lane_route(world,direction=label),points[:13])
            shape=three_lane_section(points[0])
            self.assertAlmostEqual(abs(shape['right_road_edge_xy'][1]-shape['left_road_edge_xy'][1]),10.5)
            self.assertFalse(shape['applicable_lane_rule_verified'])

    def test_rejects_wrong_center_direction_and_gap(self):
        right,center,far=section(0)
        center.transform.get_forward_vector=lambda:NS(x=-1,y=0)
        with self.assertRaisesRegex(ValueError,'direction pattern'):
            three_lane_neighbors(right)
        right,center,far=section(0)
        far.transform.location.y=-5
        with self.assertRaisesRegex(ValueError,'not joined'):
            three_lane_neighbors(right)


if __name__=='__main__':
    unittest.main()
