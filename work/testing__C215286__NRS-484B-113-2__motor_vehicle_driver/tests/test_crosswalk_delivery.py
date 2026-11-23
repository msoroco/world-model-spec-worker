import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("crosswalk_delivery", ROOT / "crosswalk_delivery.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

HASH = "a" * 64
CROSS = [(0, 0), (2, 0), (2, 4), (0, 4)]


def source():
    return {"map_name": "Town", "map_sha256": HASH, "crosswalk_source": "native:landmark/8",
            "crosswalk_polygon_xy": CROSS, "vehicle_blueprint_id": "vehicle.car",
            "spawn_transform_source": "native:waypoint/2", "reverse_route_xy": [(5, 2), (1, 2)],
            "driver_source": "native:ego/4", "district_source": "map:residential/1"}


def frame(index, relation):
    x = {"disjoint": 3.0, "contact": 2.0, "overlap": 1.5}[relation]
    return {"frame": index, "time_s": index * .05, "vehicle_actor_id": 4,
            "body_polygon_xy": [(x, 1), (x + 1, 1), (x + 1, 2), (x, 2)],
            "crosswalk_polygon_xy": CROSS, "velocity_xy": (-1, 0),
            "forward_xy": (1, 0), "reverse_gear": True}


def measured(name, relation):
    return module.measure([frame(0, relation), frame(1, relation)],
                          source_id=name, map_sha256=HASH,
                          crosswalk_source="native:landmark/8", vehicle_actor_id=4)


class GeometryTests(unittest.TestCase):
    def test_three_relations(self):
        for relation in ("disjoint", "contact", "overlap"):
            self.assertEqual(measured(relation, relation)["frames"][0]["relation"], relation)

    def test_no_crosswalk_source(self):
        packet = source()
        packet["crosswalk_source"] = ""
        with self.assertRaises(ValueError):
            module.validate_source(packet)

    def test_invalid_route(self):
        packet = source()
        packet["reverse_route_xy"] = [(1, 1), (1, 1)]
        with self.assertRaises(ValueError):
            module.validate_source(packet)

    def test_missing_original_frame(self):
        f = frame(0, "overlap")
        del f["body_polygon_xy"]
        with self.assertRaises(ValueError):
            module.measure([f], source_id="s", map_sha256=HASH,
                           crosswalk_source="c", vehicle_actor_id=4)

    def test_wrong_frequency(self):
        frames = [frame(0, "overlap"), frame(1, "overlap")]
        frames[1]["time_s"] = .1
        with self.assertRaises(ValueError):
            module.measure(frames, source_id="s", map_sha256=HASH,
                           crosswalk_source="c", vehicle_actor_id=4)

    def test_no_reverse_motion(self):
        f = frame(0, "overlap")
        f["velocity_xy"] = (0, 0)
        with self.assertRaises(ValueError):
            module.measure([f], source_id="s", map_sha256=HASH,
                           crosswalk_source="c", vehicle_actor_id=4)

    def test_audit_positive_negative(self):
        m = measured("s", "overlap")
        self.assertEqual(module.audit(m, expected_relation="overlap")["frame_count"], 2)
        with self.assertRaises(ValueError):
            module.audit(m, expected_relation="contact")

    def test_comparison_positive_negative(self):
        left, right = measured("a", "disjoint"), measured("b", "overlap")
        self.assertEqual(module.compare(left, right, changed_target="overlap")["sources"], ["a", "b"])
        with self.assertRaises(ValueError):
            module.compare(left, left, changed_target="overlap")
        with self.assertRaises(ValueError):
            module.compare(right, measured("c", "overlap"), changed_target="overlap")


class NativeTests(unittest.TestCase):
    def test_spawn_and_control(self):
        class BP:
            id = "vehicle.car"
        class Library:
            def find(self, name):
                self.name = name
                return BP()
        class Actor:
            type_id = "vehicle.car"
            def apply_control(self, value):
                self.command = value
            def destroy(self):
                self.destroyed = True
        class World:
            def get_map(self):
                return type("Map", (), {"name": "Town"})()
            def get_blueprint_library(self):
                return Library()
            def try_spawn_actor(self, bp, transform):
                self.bp, self.transform = bp, transform
                return Actor()
        world = World()
        built = module.construct(world, source(), object())
        self.assertEqual(built["ego"].type_id, "vehicle.car")
        self.assertTrue(module.control_step(built["ego"], reverse=True, hold=False,
                                            control_factory=lambda **kw: kw)["reverse"])
        self.assertEqual(module.control_step(built["ego"], reverse=True, hold=True,
                                             control_factory=lambda **kw: kw)["brake"], 1.0)
        built["cleanup"]()
        self.assertTrue(built["ego"].destroyed)

    def test_source_map_readback(self):
        class World:
            def get_map(self):
                return type("Map", (), {"name": "Different"})()
        with self.assertRaises(ValueError):
            module.construct(World(), source(), object())


if __name__ == "__main__":
    unittest.main()
