import copy
import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest
from types import SimpleNamespace


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("median_opening", ROOT / "median_opening.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def scene(case="precedence"):
    return {
        "case_id": f"testing__C125697__NRS-484B-250-1__motor_vehicle_driver__{case}",
        "crossing": {"id": "median-crossing-1", "kind": "median_opening_roadway_crossing",
                     "bounds_xy_m": [-2, -2, 2, 2],
                     "opendrive_sha256": hashlib.sha256(b"inspected map").hexdigest()},
        "ego_highway": "north-south", "other_highway": "east-west",
        "highway_identity_source": "road inventory", "public_access_source": "road inventory",
        "device_inventory_source": "original signal inventory",
        "governing_signal": {"kind": "official_traffic_signal", "readback_state": "inoperative",
                             "controlled_approach_road_ids": [1, 2]},
        "ego_approach_road_id": 1, "other_approach_road_id": 2,
        "ego_blueprint": "vehicle.car.ego", "other_blueprint": "vehicle.car.other",
        "ego_route_xy_m": [[0, -10], [0, 0], [0, 10]],
        "other_route_xy_m": [[-10, 0], [0, 0], [10, 0]],
    }


def body(x, y):
    return [[x-.2, y-.2], [x+.2, y-.2], [x+.2, y+.2], [x-.2, y+.2]]


def trace(s, ego_entry=60, other_entry=40):
    frames = []
    for i in range(900):
        ego_y = -10 if i < ego_entry else (0 if i < ego_entry+10 else 10)
        other_x = -10 if i < other_entry else (0 if i < other_entry+10 else 10)
        frames.append({"frame": i, "time_s": i/20, "signal_readback": "inoperative",
                       "ego": {"id": 10, "road_id": 1, "body_vertices_xy_m": body(0, ego_y)},
                       "other": {"id": 11, "road_id": 2, "body_vertices_xy_m": body(other_x, 0)}})
    return {"case_id": s["case_id"], "map_sha256": s["crossing"]["opendrive_sha256"],
            "actor_ids": {"ego": 10, "other": 11}, "frames": frames}


class MedianOpeningTests(unittest.TestCase):
    def test_original_source_seal_and_missing_camera(self):
        s = scene()
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            bodies = {"native_trace": json.dumps(trace(s)).encode(),
                      "opendrive": b"inspected map", "device_inventory": b"source device inventory",
                      "camera_front": b"front", "camera_rear": b"rear",
                      "camera_left": b"left", "camera_right": b"right"}
            refs = {}
            for name, data in bodies.items():
                (root / name).write_bytes(data)
                refs[name] = {"path": name, "sha256": hashlib.sha256(data).hexdigest()}
            manifest = {"case_id": s["case_id"], "frame_count": 900, "sources": refs}
            receipt = MODULE.audit_saved_sources(root, manifest, s)
            self.assertFalse(receipt["physical_pixels_reviewed"])
            self.assertTrue(receipt["observations"]["other_entered_before_ego"])
            (root / "camera_left").unlink()
            with self.assertRaisesRegex(ValueError, "missing original source"):
                MODULE.audit_saved_sources(root, manifest, s)
            (root / "camera_left").write_bytes(b"altered")
            with self.assertRaisesRegex(ValueError, "stale original source"):
                MODULE.audit_saved_sources(root, manifest, s)

    def test_native_construction_and_rollback(self):
        class Map:
            def to_opendrive(self):
                return "inspected map"

            def get_waypoint(self, location, project_to_road=False):
                self_outer.assertFalse(project_to_road)
                return SimpleNamespace(transform=SimpleNamespace(location=location),
                                       road_id=1 if location.y != 0 else 2,
                                       is_junction=location.x == 0 and location.y == 0)

        class Actor:
            destroyed = False

            def destroy(self):
                self.destroyed = True

        class World:
            def __init__(self, fail=False):
                self.fail = fail
                self.actors = []

            def get_map(self):
                return Map()

            def try_spawn_actor(self, blueprint, transform):
                if self.fail and self.actors:
                    return None
                actor = Actor()
                self.actors.append(actor)
                return actor

        self_outer = self
        s = scene()
        # Map's road ID is determined by its approach: the two starts differ.
        s["ego_route_xy_m"] = [[0, -10], [0, 0], [0, 10]]
        s["other_route_xy_m"] = [[-10, 0], [0, 0], [10, 0]]
        # The first ego waypoint has road ID 1, first other waypoint ID 2.
        library = SimpleNamespace(find=lambda name: name)
        loc = lambda x, y: SimpleNamespace(x=x, y=y)
        world = World()
        actors, routes = MODULE.construct_native(world, s, loc, library, lambda _: "inoperative")
        self.assertEqual(set(actors), {"ego", "other"})
        self.assertEqual(len(routes["ego"]), 3)
        failing = World(fail=True)
        with self.assertRaisesRegex(ValueError, "other spawn failed"):
            MODULE.construct_native(failing, s, loc, library, lambda _: "inoperative")
        self.assertTrue(failing.actors[0].destroyed)
        with self.assertRaisesRegex(ValueError, "live governing signal"):
            MODULE.construct_native(World(), s, loc, library, lambda _: "green")

    def test_scene_and_measurement(self):
        s = scene()
        self.assertEqual(MODULE.validate_scene(s, "inspected map"), "median-crossing-1")
        result = MODULE.measure_saved(trace(s), s)
        self.assertTrue(result["other_entered_before_ego"])
        self.assertTrue(result["ego_waited_until_other_exit"])
        self.assertEqual(result["legal_judgment"], "unresolved")

    def test_comparison(self):
        a, b = scene(), scene("advance")
        first = MODULE.measure_saved(trace(a, 60), a)
        second = MODULE.measure_saved(trace(b, 45), b)
        self.assertFalse(second["ego_waited_until_other_exit"])
        self.assertEqual(MODULE.audit_comparison(first, second, a, b)["difference"],
                         "measured ego crossing entry relative to other exit")

    def test_source_rejections(self):
        s = scene()
        with self.assertRaisesRegex(ValueError, "OpenDRIVE"):
            MODULE.validate_scene(s, "wrong map")
        altered = copy.deepcopy(s)
        altered["governing_signal"]["readback_state"] = "operating"
        with self.assertRaisesRegex(ValueError, "inoperative"):
            MODULE.validate_scene(altered, "inspected map")
        altered = copy.deepcopy(s)
        altered["other_route_xy_m"] = [[-10, 5], [0, 5], [10, 5]]
        with self.assertRaisesRegex(ValueError, "does not cross"):
            MODULE.validate_scene(altered, "inspected map")
        saved = trace(s)
        saved["frames"].pop(10)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            MODULE.measure_saved(saved, s)
        saved = trace(s)
        saved["frames"][50]["signal_readback"] = "green"
        with self.assertRaisesRegex(ValueError, "inoperative"):
            MODULE.measure_saved(saved, s)

    def test_comparison_rejects_changed_fixed_source(self):
        a, b = scene(), scene("advance")
        first = MODULE.measure_saved(trace(a, 60), a)
        second = MODULE.measure_saved(trace(b, 45), b)
        b["other_highway"] = "different road"
        with self.assertRaisesRegex(ValueError, "fixed condition"):
            MODULE.audit_comparison(first, second, a, b)

    def test_request_is_not_observation(self):
        self.assertEqual(MODULE.requested_ego_control(True, True, True), "brake")
        self.assertEqual(MODULE.requested_ego_control(True, False, False), "brake")
        self.assertEqual(MODULE.requested_ego_control(True, False, True), "proceed")


if __name__ == "__main__":
    unittest.main()
