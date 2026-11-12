import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from one_way_construction import (adjacent_same_direction_left,one_way_section,
                                  select_one_way_route,spawn_one_way_sign)


def pair(x,direction=1):
    def make(lane_id,y):
        return NS(road_id=9,lane_id=lane_id,lane_width=3.5,is_junction=False,
            transform=NS(location=NS(x=x,y=y,z=0),rotation=object(),
                         get_forward_vector=lambda:NS(x=direction,y=0)))
    right=make(-1*direction,1.75*direction)
    left=make(-2*direction,-1.75*direction)
    right.get_right_lane=lambda:None
    right.get_left_lane=lambda:left
    left.get_left_lane=lambda:None
    return right,left


class OneWayConstructionTests(unittest.TestCase):
    def test_geometry_and_route_both_directions(self):
        for direction,label in ((1,'east'),(-1,'west')):
            points=[pair(i*2.5*direction,direction)[0] for i in range(14)]
            for i,point in enumerate(points):
                point.next=lambda step,i=i:[points[i+1]] if i+1<len(points) else []
            world=NS(get_spawn_points=lambda:[NS(location=NS(x=0,y=1.75*direction))],
                     get_waypoint=lambda _:points[0])
            self.assertEqual(select_one_way_route(world,direction=label),points[:13])
            left=adjacent_same_direction_left(points[0])
            section=one_way_section(points[0],left)
            self.assertEqual(section['road_id'],9)
            self.assertAlmostEqual(abs(section['right_road_edge_xy'][1]-section['left_road_edge_xy'][1]),7.0)

    def test_rejects_opposing_lane_and_spawns_sign_at_roadside(self):
        right,left=pair(0)
        left.transform.get_forward_vector=lambda:NS(x=-1,y=0)
        with self.assertRaisesRegex(ValueError,'another direction'):
            adjacent_same_direction_left(right)
        right,left=pair(0)
        bp=NS(id='static.prop.oneway')
        positions=[]
        world=NS(get_blueprint_library=lambda:NS(filter=lambda pattern:[bp] if pattern=='*oneway*' else []),
                 try_spawn_actor=lambda blueprint,transform:positions.append(transform.location) or NS(id=12))
        carla=NS(Location=lambda **kw:NS(**kw),Transform=lambda loc,rot:NS(location=loc,rotation=rot))
        self.assertEqual(spawn_one_way_sign(world,carla,right).id,12)
        self.assertGreater(positions[0].y,right.transform.location.y)
        world.get_blueprint_library=lambda:NS(filter=lambda pattern:[])
        with self.assertRaisesRegex(ValueError,'blueprint unavailable'):
            spawn_one_way_sign(world,carla,right)


if __name__=='__main__':
    unittest.main()
