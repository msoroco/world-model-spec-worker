import copy
import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("through_highway", ROOT / "through_highway.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
audit_spec = importlib.util.spec_from_file_location("delivery_audit", ROOT / "delivery_audit.py")
audit = importlib.util.module_from_spec(audit_spec)
audit_spec.loader.exec_module(audit)
SEAL = "a" * 64


def site(maneuver="cross"):
    site_packet = {"law_id": module.LAW, "cell_id": "C179789", "map_sha256": SEAL,
            "map_name": "ReviewedTown", "intersection_id": "junction-7",
            "municipal_jurisdiction_source": "review/jurisdiction",
            "through_highway_designation_source": "review/designation",
            "intersection_geometry_source": "map/junction-7",
            "entrance_control_source": "review/entrance-device",
            "antecedent_review_source": "review/antecedent-pending",
            "road_kind": "paved_road", "control_kind": "other_vehicle",
            "conflict_box_xy": [-3, -3, 3, 3], "entering_maneuver": maneuver,
            "routes": {
                "through": {"road_id": 1, "lane_id": 1, "direction_source": "map/through",
                            "route_source": "map/through-route", "waypoints_xyz": [[-20, 0, 0], [0, 0, 0], [20, 0, 0]]},
                "entering": {"road_id": 2, "lane_id": -1, "direction_source": "map/side",
                             "route_source": "map/side-route", "waypoints_xyz": [[0, -20, 0], [0, 0, 0], [0, 20, 0]]}}}
    if maneuver == "enter":
        site_packet["routes"]["entering"]["waypoints_xyz"][-1] = [20, 0, 0]
    return site_packet


def frames():
    rows = []
    for i in range(420):
        rows.append({"frame_index": i, "native_frame": 100 + i, "time_s": i / 20,
                     "map_sha256": SEAL, "intersection_id": "junction-7",
                     "through": {"actor_id": 1, "alive": True, "center_xy": [-20 + i * 0.1, 0], "speed_mps": 2.0},
                     "entering": {"actor_id": 2, "alive": True, "center_xy": [0, -20 + i * 0.1],
                                  "speed_mps": 2.0 if i < 100 else 0.0 if i < 130 else 2.0}})
    return rows


class ThroughHighwayTests(unittest.TestCase):
    def test_native_snapshot_adapter_reads_both_original_actors(self):
        class Vector:
            def __init__(self, x, y, z=0):
                self.x, self.y, self.z = x, y, z

        class Actor:
            is_alive = True

            def __init__(self, identity, x, y, speed):
                self.id, self.x, self.y, self.speed = identity, x, y, speed

            def get_location(self):
                return Vector(self.x, self.y)

            def get_velocity(self):
                return Vector(self.speed, 0)

        class Snapshot:
            frame = 517
            timestamp = type("Timestamp", (), {"elapsed_seconds": 25.0})()

        class World:
            def get_map(self):
                return type("Map", (), {"name": "ReviewedTown"})()

            def get_snapshot(self):
                return Snapshot()

        world = World()
        actors = {"through": Actor(1, -20, 0, 2), "entering": Actor(2, 0, -20, 3)}
        row = module.sample_native_frame(world, actors, site(), "cross_yield", SEAL, 0, 25.0)
        self.assertEqual(row["native_frame"], 517)
        self.assertEqual(row["through"]["center_xy"], [-20, 0])
        self.assertEqual(row["entering"]["speed_mps"], 3)
        with self.assertRaisesRegex(ValueError, "cadence"):
            module.sample_native_frame(world, actors, site(), "cross_yield", SEAL, 1, 25.0)
        actors["entering"].id = 1
        with self.assertRaisesRegex(ValueError, "same Native actor"):
            module.sample_native_frame(world, actors, site(), "cross_yield", SEAL, 0, 25.0)

    def test_four_cases_keep_antecedent_unresolved(self):
        for key in module.CASES:
            report = module.measure(site(module.CASES[key][0]), key, SEAL, frames())
            self.assertEqual(report["original_frame_count"], 420)
            self.assertEqual(report["antecedent_legal_review"], "unresolved")
            self.assertEqual(report["right_of_way_legal_review"], "unresolved")
            self.assertEqual(report["entering_preentry_min_speed_mps"], 0.0)

    def test_site_rejects_unreviewed_context_and_wrong_route(self):
        packet = site()
        packet.pop("through_highway_designation_source")
        with self.assertRaisesRegex(ValueError, "designation_source"):
            module.validate_site(packet, "cross_yield", SEAL)
        packet = site()
        packet["routes"]["entering"]["road_id"] = 1
        with self.assertRaisesRegex(ValueError, "distinct intersection"):
            module.validate_site(packet, "cross_yield", SEAL)
        with self.assertRaisesRegex(ValueError, "enter/cross route"):
            module.validate_site(site("enter"), "cross_yield", SEAL)
        packet = site("enter")
        packet["routes"]["entering"]["waypoints_xyz"][-1] = [0, 20, 0]
        with self.assertRaisesRegex(ValueError, "does not merge"):
            module.validate_site(packet, "enter_yield", SEAL)

    def test_original_source_rejections(self):
        bad = frames()
        bad[200]["native_frame"] = None
        with self.assertRaisesRegex(ValueError, "frame identity"):
            module.measure(site(), "cross_yield", SEAL, bad)
        bad = frames()
        bad[200]["native_frame"] = bad[199]["native_frame"]
        with self.assertRaisesRegex(ValueError, "Native frame nonconsecutive"):
            module.measure(site(), "cross_yield", SEAL, bad)
        bad = frames()
        for i in range(200, len(bad)):
            bad[i]["native_frame"] += 1
        with self.assertRaisesRegex(ValueError, "Native frame nonconsecutive"):
            module.measure(site(), "cross_yield", SEAL, bad)
        bad = frames()
        bad[200]["entering"]["actor_id"] = 3
        with self.assertRaisesRegex(ValueError, "actor identity changed"):
            module.measure(site(), "cross_yield", SEAL, bad)
        bad = frames()
        bad[200]["time_s"] += 0.1
        with self.assertRaisesRegex(ValueError, "time join"):
            module.measure(site(), "cross_yield", SEAL, bad)
        bad = frames()
        for row in bad:
            row["entering"]["center_xy"] = [20, 20]
        with self.assertRaisesRegex(ValueError, "traversal"):
            module.measure(site(), "cross_yield", SEAL, bad)

    def test_comparison_rejects_missing_or_changed_fixed_context(self):
        a = module.measure(site(), "cross_yield", SEAL, frames())
        b = module.measure(site(), "cross_continue", SEAL, frames())
        self.assertEqual(len(module.compare([a, b], ["cross_yield", "cross_continue"])["case_ids"]), 2)
        with self.assertRaisesRegex(ValueError, "pair missing"):
            module.compare([a], ["cross_yield", "cross_continue"])
        bad = copy.deepcopy(b)
        bad["intersection_id"] = "elsewhere"
        with self.assertRaisesRegex(ValueError, "fixed site"):
            module.compare([a, bad], ["cross_yield", "cross_continue"])

    def test_native_spawn_and_cleanup(self):
        class Location:
            def __init__(self, *xyz): self.xyz = xyz
        class Map:
            name = "ReviewedTown"
            def __init__(self, fail_lane=False): self.fail_lane = fail_lane
            def get_waypoint(self, loc, project_to_road=False):
                road_id = 1 if loc.xyz[0] == -20 else 2
                lane_id = 1 if road_id == 1 else (-2 if self.fail_lane else -1)
                return type("WP", (), {"road_id": road_id, "lane_id": lane_id, "transform": loc.xyz})()
        class Actor:
            def __init__(self): self.destroyed = False
            def destroy(self): self.destroyed = True
        class World:
            def __init__(self, fail_lane=False):
                self.map = Map(fail_lane)
                self.spawned = []
            def get_map(self): return self.map
            def get_blueprint_library(self): return self
            def find(self, identity): return identity
            def try_spawn_actor(self, blueprint, transform):
                actor = Actor()
                self.spawned.append(actor)
                return actor
        old = sys.modules.get("carla")
        sys.modules["carla"] = type("Carla", (), {"Location": Location})
        try:
            world = World()
            built = module.construct(world, site(), "cross_yield", SEAL)
            self.assertEqual(set(built["actors"]), {"through", "entering"})
            self.assertEqual(len(world.spawned), 2)
            world = World(True)
            with self.assertRaisesRegex(ValueError, "Native lane"):
                module.construct(world, site(), "cross_yield", SEAL)
            self.assertTrue(world.spawned[0].destroyed)
        finally:
            if old is None: sys.modules.pop("carla", None)
            else: sys.modules["carla"] = old

    def test_native_controller_uses_velocity_and_waypoint(self):
        class VehicleControl:
            def __init__(self, **kwargs): self.values = kwargs
        class Actor:
            def get_velocity(self): return type("V", (), {"x": 3.0, "y": 0.0, "z": 0.0})()
            def get_transform(self):
                return type("T", (), {"location": type("L", (), {"x": 0.0, "y": 0.0})(),
                                       "get_forward_vector": lambda self: type("F", (), {"x": 1.0, "y": 0.0})()})()
            def apply_control(self, value): self.control = value
        old = sys.modules.get("carla")
        sys.modules["carla"] = type("Carla", (), {"VehicleControl": VehicleControl})
        try:
            actor = Actor()
            report = module.control_tick(actor, [10, 2, 0], 6.0)
            self.assertGreater(report["throttle"], 0)
            self.assertGreater(report["steer"], 0)
            report = module.control_tick(actor, [10, 2, 0], 6.0, allow_go=False)
            self.assertGreater(report["brake"], 0)
        finally:
            if old is None: sys.modules.pop("carla", None)
            else: sys.modules["carla"] = old

    def test_saved_audit_accepts_sealed_original_sources_and_rejects_stale(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            def ref(name):
                path = root / name
                path.write_text(name, encoding="utf-8")
                return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            measured = module.measure(site(), "cross_yield", SEAL, frames())
            source = {"case_id": measured["case_id"], "map_sha256": SEAL,
                      "intersection_id": "junction-7", "native_result": ref("native"),
                      "municipal_jurisdiction": ref("jurisdiction"),
                      "through_highway_designation": ref("designation"),
                      "entrance_control": ref("control"), "antecedent_review": ref("antecedent"),
                      "frame_map": [{"frame_index": i, "native_frame": 100 + i, "time_s": i / 20}
                                    for i in range(420)],
                      "cameras": {name: dict(ref(name), decoded_frames=420,
                                             original_frame_first=0, original_frame_last=419)
                                  for name in audit.CAMERAS}, "physical_completion": True}
            self.assertEqual(audit.audit_saved(source, measured)["original_frame_count"], 420)
            bad = copy.deepcopy(source)
            bad["through_highway_designation"]["sha256"] = "b" * 64
            with self.assertRaisesRegex(ValueError, "designation source seal"):
                audit.audit_saved(bad, measured)
            bad = copy.deepcopy(source)
            bad["cameras"].pop("approach")
            with self.assertRaisesRegex(ValueError, "four camera"):
                audit.audit_saved(bad, measured)
            bad = copy.deepcopy(source)
            bad["frame_map"][200]["time_s"] += 0.1
            with self.assertRaisesRegex(ValueError, "time join"):
                audit.audit_saved(bad, measured)
            bad = copy.deepcopy(source)
            bad["frame_map"][200]["native_frame"] += 1
            with self.assertRaisesRegex(ValueError, "frame/time join"):
                audit.audit_saved(bad, measured)
            bad_measured = copy.deepcopy(measured)
            bad_measured["original_samples"][200]["native_frame"] += 1
            with self.assertRaisesRegex(ValueError, "measurement frame/time join"):
                audit.audit_saved(source, bad_measured)
            other = module.measure(site(), "cross_continue", SEAL, frames())
            other_source = dict(source, case_id=other["case_id"])
            self.assertEqual(len(audit.audit_comparison(source, measured, other_source, other)["case_ids"]), 2)
            bad_other = dict(other, map_sha256="c" * 64)
            with self.assertRaisesRegex(ValueError, "map or intersection"):
                audit.audit_saved(other_source, bad_other)


if __name__ == "__main__":
    unittest.main()
