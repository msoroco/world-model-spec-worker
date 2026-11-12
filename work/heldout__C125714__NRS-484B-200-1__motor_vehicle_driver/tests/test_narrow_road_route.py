import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from narrow_road_route import select_narrow_median_route
from test_directed_geometry import lane
from test_median_opening_route import reference


def narrow_map(width):
    points=[lane(-1,i*2.5,width/2,1,width=width) for i in range(14)]
    for i,point in enumerate(points):
        point.is_junction=False
        point.get_left_lane=lambda i=i: lane(1,i*2.5,-width/2,-1,width=width)
        point.next=lambda step,i=i: [points[i+1]] if i+1<len(points) else []
    return NS(name='CPU-test-map',get_spawn_points=lambda:[NS(location=NS(x=0,y=width/2))],
              get_waypoint=lambda _:points[0]),points


class NarrowRouteTests(unittest.TestCase):
    def test_selects_joined_narrow_median_route(self):
        world,points=narrow_map(2.2)
        route,samples,widths=select_narrow_median_route(world,reference())
        self.assertEqual(route,points[:13])
        self.assertGreaterEqual(len(samples),2)
        self.assertEqual(widths,[4.4]*13)
        wide,_=narrow_map(3.0)
        with self.assertRaisesRegex(ValueError,'wider than engineered target'):
            select_narrow_median_route(wide,reference())


if __name__=='__main__':
    unittest.main()
