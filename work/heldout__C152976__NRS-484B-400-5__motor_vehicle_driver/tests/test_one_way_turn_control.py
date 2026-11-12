import importlib.util
from pathlib import Path
import sys
import unittest

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from one_way_left import CASES
spec = importlib.util.spec_from_file_location('one_way_turn_control', root/'one_way_turn_control.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Obj:
    def __init__(self, **kw): self.__dict__.update(kw)
class WP:
    def __init__(self, road, x, y, yaw):
        self.road_id = road
        self.transform = Obj(location=Obj(x=x,y=y), rotation=Obj(yaw=yaw))
class Actor:
    is_alive = True
    def __init__(self, x, y, yaw, speed=0):
        self.transform = Obj(location=Obj(x=x,y=y),rotation=Obj(yaw=yaw))
        self.velocity = Obj(x=speed,y=0)
        self.last_control = None
    def get_transform(self): return self.transform
    def get_velocity(self): return self.velocity
    def apply_control(self, control): self.last_control = control
class Carla:
    @staticmethod
    def VehicleControl(**kw): return Obj(**kw)


class ControlTests(unittest.TestCase):
    def survey(self):
        route=[WP(1,-4.5,-20,90),WP(1,-4.5,-10,90),
               WP(3,-6,-6,135),WP(2,-10,-4.5,180),WP(2,-20,-4.5,180)]
        return {'approach':route[0],'departure':route[-1], 'connected_route':route}
    def test_lateral_sweeps_apply_to_correct_roads(self):
        survey = self.survey()
        base = m.target_route_points(survey,CASES['left_edge_reference'])
        approach = m.target_route_points(survey,CASES['approach_shifted_right'])
        departure = m.target_route_points(survey,CASES['departure_shifted_right'])
        self.assertAlmostEqual(approach[0][0]-base[0][0],1)
        self.assertAlmostEqual(approach[-1][1]-base[-1][1],0)
        self.assertAlmostEqual(departure[0][0]-base[0][0],0)
        self.assertAlmostEqual(departure[-1][1]-base[-1][1],1)
        self.assertNotEqual(approach[2],base[2])
        self.assertNotEqual(departure[2],base[2])
    def test_bounded_control_tracks_both_approach_and_departure(self):
        points=m.target_route_points(self.survey(),CASES['left_edge_reference'])
        approach=Actor(-4.5,-20,90)
        row=m.command(approach,Carla,points)
        self.assertGreater(approach.last_control.throttle,0)
        self.assertEqual(row['requested_target_mps'],5)
        departure=Actor(-10,-4.5,180,8)
        row=m.command(departure,Carla,points)
        self.assertGreater(departure.last_control.brake,0)
        self.assertLessEqual(abs(row['requested_steer']),.5)
    def test_missing_actor_and_bad_route_rejected(self):
        points=m.target_route_points(self.survey(),CASES['left_edge_reference'])
        with self.assertRaisesRegex(ValueError,'actor absent'):m.command(None,Carla,points)
        with self.assertRaisesRegex(ValueError,'invalid route'):m.command(Actor(0,0,0),Carla,points[:1])


if __name__ == '__main__': unittest.main()
