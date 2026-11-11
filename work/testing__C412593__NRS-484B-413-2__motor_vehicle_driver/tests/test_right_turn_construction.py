import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT=Path(__file__).resolve().parents[1]


def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+".py"))
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


route=load("right_turn_construction")
signal=load("turn_signal_control")


def wp(x,y,road=1,lane=-1):
    return NS(road_id=road,lane_id=lane,transform=NS(location=NS(x=x,y=y)))


class RightTurnTests(unittest.TestCase):
    def test_native_spawn_route_and_cleanup(self):
        approach=[wp(x,0) for x in range(0,101,2)]
        outgoing=[wp(100,-2,2),wp(100,-4,2)]
        destroyed=[]
        actor=NS(get_location=lambda:approach[0].transform.location,
                 destroy=lambda:destroyed.append(True))
        native_map=NS(get_waypoint=lambda location,project_to_road:approach[0])
        world=NS(try_spawn_actor=lambda blueprint,transform:actor,
                 get_map=lambda:native_map)
        with route.spawn_right_turn_vehicle(world,"blueprint",approach,outgoing) as built:
            self.assertEqual(built["route"]["direct_approach_m"],100)
            self.assertAlmostEqual(built["route"]["turn_angle_degrees"],-90)
        self.assertEqual(destroyed,[True])

    def test_short_approach_and_wrong_turn_rejected(self):
        short=[wp(x,0) for x in range(0,51,2)]
        outgoing=[wp(50,-2,2),wp(50,-4,2)]
        with self.assertRaisesRegex(ValueError,"shorter"):
            route.verify_route(short,outgoing)
        long=[wp(x,0) for x in range(0,101,2)]
        wrong=[wp(100,2,2),wp(100,4,2)]
        with self.assertRaisesRegex(ValueError,"right turn"):
            route.verify_route(long,wrong)

    def test_native_right_blinker_readback_preserves_other_lights(self):
        class State:
            RightBlinker=8
        class Vehicle:
            lights=1
            def get_light_state(self):return self.lights
            def set_light_state(self,value):self.lights=value
        actor=Vehicle()
        self.assertTrue(signal.set_right_indicator(actor,State,True)["readback_right_indicator"])
        self.assertEqual(actor.lights,9)
        self.assertFalse(signal.set_right_indicator(actor,State,False)["readback_right_indicator"])
        self.assertEqual(actor.lights,1)


if __name__ == "__main__":
    unittest.main()
