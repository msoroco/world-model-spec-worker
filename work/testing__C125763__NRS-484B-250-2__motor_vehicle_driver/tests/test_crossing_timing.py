import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("crossing_timing", PACKAGE / "crossing_timing.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CONSTRUCTION_SPEC = importlib.util.spec_from_file_location("native_construction", PACKAGE / "native_construction.py")
CONSTRUCTION = importlib.util.module_from_spec(CONSTRUCTION_SPEC)
CONSTRUCTION_SPEC.loader.exec_module(CONSTRUCTION)


def body(x):
    return [[x - .4, -.4], [x + .4, -.4], [x + .4, .4], [x - .4, .4]]


class TimingTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        road = "<OpenDRIVE/>\n"
        site = {"map_sha256": hashlib.sha256(road.encode()).hexdigest(),
                "reviewer": "fixture reviewer", "source_citation": "fixture only",
                "cell_id": "C125763", "control": "yield_sign",
                "ego_highway": "A", "other_highway": "B",
                "approach_relation": "crossing", "ego_side": "left",
                "ego_actor_id": 10, "other_actor_id": 11,
                "intersection_bounds_xy_m": [0, -1, 2, 1]}
        values = {"road.xodr": road, "site-context.json": json.dumps(site) + "\n"}
        for name, actor_id, positions in (("ego", 10, [-2, -1, 0, 1]),
                                          ("other", 11, [-2, -2, -1, 0])):
            rows = [{"frame": i + 100, "time_s": i * .05,
                     "actor_id": actor_id, "body_vertices_xy_m": body(x)}
                    for i, x in enumerate(positions)]
            values[name + "-body-history.jsonl"] = "".join(json.dumps(r) + "\n" for r in rows)
        self.values = values
        self.write_all()

    def write_all(self):
        manifest = {}
        for name, value in self.values.items():
            (self.root / name).write_text(value)
            manifest[name] = {"kind": "original_native", "sha256": hashlib.sha256(value.encode()).hexdigest()}
        (self.root / "source-manifest.json").write_text(json.dumps(manifest) + "\n")

    def test_bracket_and_no_legal_verdict(self):
        result = MODULE.measure(self.root)
        self.assertAlmostEqual(result["intersection_entry_time_difference_s"], -.05)
        self.assertEqual(result["ego_entry"]["upper_frame"], 102)
        self.assertEqual(result["other_entry"]["upper_frame"], 103)
        self.assertAlmostEqual(result["difference_bracket_s"][0], -.1)
        self.assertAlmostEqual(result["difference_bracket_s"][1], 0.0)
        self.assertFalse(result["legal_verdict_claimed"])
        self.assertTrue(result["official_device_present"])

    def test_stale_source_rejected(self):
        with (self.root / "ego-body-history.jsonl").open("a") as stream:
            stream.write("{}\n")
        with self.assertRaisesRegex(ValueError, "stale original Native"):
            MODULE.measure(self.root)

    def test_join_and_device_rejected(self):
        site = json.loads(self.values["site-context.json"])
        site["control"] = "none"
        self.values["site-context.json"] = json.dumps(site) + "\n"
        self.write_all()
        with self.assertRaisesRegex(ValueError, "scope"):
            MODULE.measure(self.root)
        site["control"] = "yield_sign"
        self.values["site-context.json"] = json.dumps(site) + "\n"
        rows = [json.loads(s) for s in self.values["other-body-history.jsonl"].splitlines()]
        rows[2]["frame"] += 1
        self.values["other-body-history.jsonl"] = "".join(json.dumps(r) + "\n" for r in rows)
        self.write_all()
        with self.assertRaisesRegex(ValueError, "join"):
            MODULE.measure(self.root)

    def test_missing_entry_rejected(self):
        rows = [json.loads(s) for s in self.values["other-body-history.jsonl"].splitlines()]
        for row in rows:
            row["body_vertices_xy_m"] = body(-3)
        self.values["other-body-history.jsonl"] = "".join(json.dumps(r) + "\n" for r in rows)
        self.write_all()
        with self.assertRaisesRegex(ValueError, "No original footprint"):
            MODULE.measure(self.root)


class FakeCarla:
    class Location:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class Rotation:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class Transform:
        def __init__(self, location, rotation):
            self.location, self.rotation = location, rotation

    class VehicleControl:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)


class FakeActor:
    def __init__(self, transform):
        self.transform, self.controls, self.destroyed = transform, [], False

    def apply_control(self, control):
        self.controls.append(control)

    def get_location(self):
        return self.transform.location

    def get_velocity(self):
        return FakeCarla.Location(x=0.0, y=0.0, z=0.0)

    def get_transform(self):
        return self.transform

    def destroy(self):
        self.destroyed = True


class FakeMap:
    def to_opendrive(self):
        return "<OpenDRIVE/>\n"

    def get_waypoint(self, location, project_to_road=False):
        self.project_to_road = project_to_road
        return type("Lane", (), {"road_id": 1 if location.x < 0 else 2,
                                  "lane_id": 1})()


class FakeWorld:
    def __init__(self):
        self.map = FakeMap()
        self.spawned = []

    def get_map(self):
        return self.map

    def get_blueprint_library(self):
        return self

    def find(self, blueprint):
        return blueprint

    def try_spawn_actor(self, blueprint, transform):
        actor = FakeActor(transform)
        self.spawned.append((blueprint, actor))
        return actor


class ConstructionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.world = FakeWorld()
        for name in ("device", "highway"):
            (self.root / (name + ".txt")).write_text(name + " source\n")
        self.site = {"map_sha256": hashlib.sha256(self.world.map.to_opendrive().encode()).hexdigest(),
                     "reviewer": "fixture only", "source_citation": "fixture only",
                     "cell_id": "C125763", "control": "yield_sign",
                     "ego_highway": "A", "other_highway": "B",
                     "approach_relation": "crossing", "ego_side": "left",
                     "ego_route": [[-5, 0, 0], [-1, 0, 0], [2, 0, 0]],
                     "other_route": [[0, -5, 0], [0, -1, 0], [0, 2, 0]],
                     "ego_lane": {"road_id": 1, "lane_id": 1},
                     "other_lane": {"road_id": 2, "lane_id": 1},
                     "ego_blueprint": "vehicle.ego", "other_blueprint": "vehicle.other"}
        for name in ("device", "highway"):
            path = self.root / (name + ".txt")
            self.site[name + "_source"] = {"path": path.name,
                                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                            "citation": "fixture only"}
        self.packet = self.root / "reviewed-site.json"
        self.write_packet()

    def write_packet(self):
        self.packet.write_text(json.dumps(self.site) + "\n")

    def test_both_approaches_spawn_and_release(self):
        scene = CONSTRUCTION.reviewed_scene(self.packet, self.world)
        ego, other = CONSTRUCTION.spawn_pair(self.world, FakeCarla, scene)
        self.assertEqual([item[0] for item in self.world.spawned], ["vehicle.ego", "vehicle.other"])
        self.assertFalse(self.world.map.project_to_road)
        self.assertAlmostEqual(other.transform.rotation.yaw, 90)
        self.assertEqual(CONSTRUCTION.control_step(FakeCarla, ego, scene["ego_route"], 0, 2), "held")
        self.assertEqual(ego.controls[-1].brake, 1)
        self.assertEqual(CONSTRUCTION.control_step(FakeCarla, ego, scene["ego_route"], 2, 2), "released")
        self.assertGreater(ego.controls[-1].throttle, 0)

    def test_map_and_source_mismatch_rejected_before_spawn(self):
        self.site["map_sha256"] = "0" * 64
        self.write_packet()
        with self.assertRaisesRegex(ValueError, "OpenDRIVE"):
            CONSTRUCTION.reviewed_scene(self.packet, self.world)
        self.assertFalse(self.world.spawned)
        self.site["map_sha256"] = hashlib.sha256(self.world.map.to_opendrive().encode()).hexdigest()
        self.write_packet()
        (self.root / "device.txt").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "stale"):
            CONSTRUCTION.reviewed_scene(self.packet, self.world)

    def test_wrong_approach_lane_rejected_before_second_spawn(self):
        scene = CONSTRUCTION.reviewed_scene(self.packet, self.world)
        scene["other_lane"] = {"road_id": 7, "lane_id": 1}
        with self.assertRaisesRegex(ValueError, "approach lane"):
            CONSTRUCTION.spawn_pair(self.world, FakeCarla, scene)
        self.assertEqual(len(self.world.spawned), 1)
        self.assertTrue(self.world.spawned[0][1].destroyed)


if __name__ == "__main__":
    unittest.main()
