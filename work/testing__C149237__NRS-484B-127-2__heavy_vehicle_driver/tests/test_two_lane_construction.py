"""CPU geometry and fake Native actor proof for the two-lane exception."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from two_lane_construction import spawn_two_lane_pair
from two_lane_site import validate_site


class Actor:
    def __init__(self,location,width):
        self.location=location;self.bounding_box=NS(extent=NS(x=5,y=width/2))
        self.destroyed=False
    def get_location(self):return self.location
    def get_transform(self):return NS(get_forward_vector=lambda:NS(x=1,y=0))
    def set_transform(self,transform):self.location=transform
    def destroy(self):self.destroyed=True


class World:
    def __init__(self,lane=-1,widths=(2.2,2.2)):
        self.lane=lane;self.widths=widths;self.actors=[];self.ticks=0
    def try_spawn_actor(self,blueprint,transform):
        actor=Actor(transform,self.widths[len(self.actors)]);self.actors.append(actor);return actor
    def get_map(self):return self
    def get_waypoint(self,location,project_to_road=False):
        if project_to_road:raise AssertionError('Sourced lane required')
        return NS(road_id=149238,lane_id=self.lane)
    def tick(self):self.ticks+=1


def transform(x,y,heading):
    if heading:raise AssertionError('Expected forward direction')
    return NS(x=x,y=y)


class TwoLaneTests(unittest.TestCase):
    def test_two_forward_driving_lanes_in_authored_map(self):
        site=validate_site()
        self.assertEqual(site['available_same_direction_lanes'],[-1,-2])
        self.assertEqual(site['same_direction_lane_count'],2)

    def test_pair_realizes_fixed_gap_and_cleans_up(self):
        world=World()
        with spawn_two_lane_pair(world,'vehicle.carlamotors.european_hgv',
                                 'vehicle.carlamotors.carlacola',transform) as pair:
            self.assertAlmostEqual(pair['initial_body_gap_m'],150)
            self.assertEqual(pair['site']['same_direction_lane_count'],2)
            self.assertEqual(world.ticks,1)
        self.assertTrue(all(a.destroyed for a in world.actors))

    def test_rejects_narrow_or_wrong_lane(self):
        for world,expected in ((World(widths=(2.0,2.2)),'80 inches'),
                               (World(lane=-2),'following lane')):
            with self.assertRaisesRegex(ValueError,expected):
                with spawn_two_lane_pair(world,'vehicle.carlamotors.european_hgv',
                                         'vehicle.carlamotors.carlacola',transform):pass
            self.assertTrue(all(a.destroyed for a in world.actors))


if __name__=='__main__':unittest.main()
