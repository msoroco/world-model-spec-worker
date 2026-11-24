"""CPU authored road, full-body clearance and CARLA frame reflection checks."""
import math
import unittest
import xml.etree.ElementTree as ET

from geometry import authored_route,check,native_route,open_drive


class GeometryTests(unittest.TestCase):
    def test_authored_hill_sign_and_opposed_lanes(self):
        summary=check()
        self.assertTrue(summary['passed'])
        self.assertFalse(summary['sign_official_native_verified'])
        root=ET.fromstring(open_drive())
        road=root.find('road')
        elevations=road.findall('elevationProfile/elevation')
        first=elevations[0]
        apex=float(first.get('a'))+80*float(first.get('b'))+80**2*float(first.get('c'))
        self.assertAlmostEqual(apex,1.6)
        self.assertAlmostEqual(float(elevations[1].get('a')),apex)
        self.assertEqual({int(row.get('id')) for row in road.findall('lanes/laneSection/*/lane')},{-1,0,1})
        self.assertEqual(road.find('signals/signal').get('name'),'no_u_turn_prohibition_proposal')

    def test_straight_and_reversal_routes_have_body_clearance(self):
        for suffix in ('witness_1','witness_2'):
            route=native_route(suffix)
            self.assertEqual(authored_route(suffix),[[x,-y] for x,y in route])
            for index,point in enumerate(route):
                before=route[max(0,index-1)];after=route[min(len(route)-1,index+1)]
                dx,dy=after[0]-before[0],after[1]-before[1]
                length=math.hypot(dx,dy);forward=(dx/length,dy/length)
                right=(-forward[1],forward[0])
                body=[(point[0]+a*forward[0]+b*right[0],
                       point[1]+a*forward[1]+b*right[1])
                      for a,b in ((-2.5,-1),(-2.5,1),(2.5,1),(2.5,-1))]
                self.assertTrue(all(-80<=x<=80 and -8<=y<=8 for x,y in body),
                                (suffix,index,point))
            if suffix=='witness_1':
                self.assertEqual(route[-1],[50,4])
            else:
                self.assertEqual(route[-1],[-50,-4])
                self.assertGreater(max(x for x,y in route),3.9)


if __name__=='__main__':unittest.main()
