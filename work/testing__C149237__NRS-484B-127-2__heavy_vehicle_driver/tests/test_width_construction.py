"""Exercise Native-style width selection and placement without CARLA."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from width_construction import WIDTH_M, spawn_width_control_pair


HGV='vehicle.carlamotors.european_hgv'
COLA='vehicle.carlamotors.carlacola'
CYBER='vehicle.tesla.cybertruck'
FIRE='vehicle.carlamotors.firetruck'


class Actor:
    def __init__(self,blueprint,location,width):
        self.blueprint=blueprint
        self.location=location
        self.bounding_box=NS(extent=NS(x=5.0,y=width/2))
        self.destroyed=False
    def get_location(self):return self.location
    def get_transform(self):return NS(get_forward_vector=lambda:NS(x=1,y=0))
    def set_transform(self,location):self.location=location
    def destroy(self):self.destroyed=True


class World:
    def __init__(self,widths,lane=-1):
        self.widths=widths;self.lane=lane;self.actors=[];self.ticks=0
    def try_spawn_actor(self,blueprint,transform):
        name=getattr(blueprint,'id',blueprint)
        actor=Actor(name,transform,self.widths[name]);self.actors.append(actor)
        return actor
    def tick(self):self.ticks+=1
    def get_map(self):return self
    def get_waypoint(self,location,project_to_road=False):
        if project_to_road:raise AssertionError('Must use original lane')
        return NS(road_id=149237,lane_id=self.lane)


def transform(x,y,heading):
    if heading!=0:raise AssertionError('Wrong authored direction')
    return NS(x=x,y=y)


class WidthConstructionTests(unittest.TestCase):
    def test_below_ego_selects_measured_narrow_truck_and_cleans_rejected_actor(self):
        world=World({HGV:2.2,COLA:2.2,CYBER:2.12,FIRE:2.0})
        with spawn_width_control_pair(world,'ego_width_below_80in',HGV,[CYBER,FIRE],transform) as pair:
            self.assertEqual(pair['realized_widths_m']['ego'],2.0)
            self.assertAlmostEqual(pair['initial_body_gap_m'],152.4)
            self.assertEqual(pair['varied_role'],'ego')
            self.assertEqual(world.ticks,1)
        self.assertTrue(all(actor.destroyed for actor in world.actors))

    def test_exact_width_boundary_uses_realized_measurement(self):
        world=World({HGV:2.2,CYBER:WIDTH_M})
        with spawn_width_control_pair(world,'ego_width_at_80in',HGV,[CYBER],transform) as pair:
            self.assertAlmostEqual(pair['realized_widths_m']['ego'],WIDTH_M)
            self.assertAlmostEqual(pair['initial_body_gap_m'],152.4)
        self.assertTrue(all(actor.destroyed for actor in world.actors))

    def test_narrow_lead_uses_distinct_role(self):
        world=World({HGV:2.2,FIRE:1.99})
        with spawn_width_control_pair(world,'lead_width_below_80in',HGV,[FIRE],transform) as pair:
            self.assertEqual(pair['varied_role'],'lead')
            self.assertEqual(pair['realized_widths_m']['ego'],2.2)
            self.assertEqual(pair['realized_widths_m']['lead'],1.99)
        self.assertTrue(all(actor.destroyed for actor in world.actors))

    def test_missing_matching_width_and_wrong_lane_reject_with_cleanup(self):
        for case,widths,lane,expected in (
            ('ego_width_below_80in',{HGV:2.2,CYBER:2.12},-1,'No pinned truck blueprint'),
            ('ego_width_at_80in',{HGV:2.2,CYBER:2.12},-1,'No pinned truck blueprint'),
            ('lead_width_below_80in',{HGV:2.2,FIRE:1.99},-2,'left authored following lane')):
            world=World(widths,lane)
            with self.assertRaisesRegex(ValueError,expected):
                with spawn_width_control_pair(world,case,HGV,[CYBER if case!='lead_width_below_80in' else FIRE],transform):pass
            self.assertTrue(all(actor.destroyed for actor in world.actors))

    def test_unclassified_blueprint_rejected_before_spawning(self):
        world=World({HGV:2.2,'vehicle.lincoln.mkz_2020':1.9})
        with self.assertRaisesRegex(ValueError,'classification'):
            with spawn_width_control_pair(world,'ego_width_below_80in',HGV,
                                          ['vehicle.lincoln.mkz_2020'],transform):pass
        self.assertEqual(world.actors,[])


if __name__=='__main__':unittest.main()
