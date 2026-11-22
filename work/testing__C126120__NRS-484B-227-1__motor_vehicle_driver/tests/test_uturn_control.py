import hashlib
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from uturn_control import apply, bind_map, next_request, validate_scene


def scene():
    return {"context": {
        "map_source_sha256": hashlib.sha256(b"inspected map").hexdigest(),
        "authority_review_source_sha256": "review hash",
        "opening_bounds_xy_m": [-1,-1,1,1],
        "closed_divider_bounds_xy_m": [[-4,-1,-1.1,1],[1.1,-1,4,1]],
        "source_right_roadway_bounds_xy_m": [-4,-4,4,-1.2],
        "destination_right_roadway_bounds_xy_m": [-4,1.2,4,4]},
        "route_xy_m": [[-3,-2],[-1,-2],[0,0],[1,2],[-3,2]],
        "segment_directions": ["forward","forward","forward","forward"],
        "vehicle_half_width_m": .2,
        "source_road_id": 10,"destination_road_id": 20}


class UTurnControlTests(unittest.TestCase):
    def test_route_corridor_and_live_map_binding(self):
        item = scene()
        self.assertEqual(validate_scene(item)["authored_direction_change_deg"],180)
        class Waypoint:
            def __init__(self,road): self.road_id=road
        class Map:
            def to_opendrive(self): return "inspected map"
            def get_waypoint(self,point,project_to_road=False):
                return Waypoint(10 if point[1]<0 else 20)
        self.assertEqual(len(bind_map(Map(),item,lambda x,y:(x,y))),2)
        item["context"]["map_source_sha256"]="wrong"
        with self.assertRaisesRegex(ValueError,"live OpenDRIVE"):
            bind_map(Map(),item,lambda x,y:(x,y))

    def test_route_corridor_rejects_closed_barrier(self):
        item=scene()
        item["route_xy_m"][2]=[2,0]
        with self.assertRaisesRegex(ValueError,"closed divider"):
            validate_scene(item)

    def test_route_touching_opening_but_crossing_around_divider_end_is_rejected(self):
        item=scene()
        item["route_xy_m"]=[[-3,-2],[-1,-2],[0,-.5],[0,-2],
                            [-5,-2],[-5,2],[5,2],[-3,2]]
        item["segment_directions"]=["forward"]*(len(item["route_xy_m"])-1)
        with self.assertRaisesRegex(ValueError,"bypasses median opening"):
            validate_scene(item)

    def test_gear_transition_requires_observed_stop_and_applies_request(self):
        item=scene()
        item["segment_directions"]=["forward","forward","reverse","forward"]
        state={"last_frame":2,"target_index":2}
        held=next_request(item,state,x=0,y=0,yaw_deg=90,speed_mps=1,frame=3)
        self.assertEqual(held["request"],"gear_transition_brake")
        self.assertEqual(held["target_index"],2)
        go=next_request(item,held,x=0,y=0,yaw_deg=90,speed_mps=0,frame=4)
        self.assertTrue(go["reverse"])
        class Actor:
            def apply_control(self,control): self.control=control
        class Carla:
            @staticmethod
            def VehicleControl(**kwargs): return kwargs
        actor=Actor();apply(actor,Carla,go)
        self.assertTrue(actor.control["reverse"])
        with self.assertRaisesRegex(ValueError,"stale"):
            next_request(item,go,x=0,y=0,yaw_deg=90,speed_mps=0,frame=4)


if __name__ == "__main__": unittest.main()
