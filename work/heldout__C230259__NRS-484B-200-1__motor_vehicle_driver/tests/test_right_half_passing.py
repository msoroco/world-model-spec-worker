"""Connected approach and return tests for the proposed passing construction."""
import sys
from pathlib import Path
import unittest
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from right_half_passing import passing_targets

class Point:
    def __init__(self,x,y): self.x,self.y=x,y
class Transform:
    def __init__(self,x,y,direction): self.location=Point(x,y);self.direction=direction
    def get_forward_vector(self):return Point(self.direction,0)
class Waypoint:
    lane_id=-1
    road_id=1
    lane_type='Driving'
    def __init__(self,x,y,direction):self.transform=Transform(x,y,direction);self.other=None
    def get_left_lane(self):return self.other
    def get_right_lane(self):return None

def route():
    items=[]
    for i in range(17):
        right=Waypoint(i*2.5,-2,1);left=Waypoint(i*2.5,2,-1)
        left.lane_id=1;right.other=left;left.other=right
        items.append(right)
    return items

class PassingTargetsTest(unittest.TestCase):
    def test_connected_departure_and_return_around_same_direction_lead(self):
        path=passing_targets(route())
        targets=path['targets_xy_m']
        self.assertEqual([point[1] for point in targets[:3]],[-2.]*3)
        self.assertEqual(targets[8][1],2.)
        self.assertEqual([point[1] for point in targets[-3:]],[-2.]*3)
        self.assertEqual(path['lead_spawn_xy_m'],[20.,-2.])
        self.assertFalse(path['physical_passing_confirmed'])
        self.assertFalse(path['governing_law_decided'])
    def test_reject_short_or_misordered_excursion(self):
        with self.assertRaisesRegex(ValueError,'approach'):
            passing_targets(route()[:12])
        with self.assertRaisesRegex(ValueError,'approach'):
            passing_targets(route(),left_entry_index=10)

if __name__=='__main__':unittest.main()
