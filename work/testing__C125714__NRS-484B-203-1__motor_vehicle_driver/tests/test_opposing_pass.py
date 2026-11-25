import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("opposing_pass", ROOT / "opposing_pass.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def site():
    rows = [{"s_m": s, "source": "native_map", "undivided": True,
             "paved_y_bounds_m": [-3.5, 3.5]} for s in range(-25, 26, 5)]
    return {"source_kind": "original_native_map_geometry", "layout": "median_opening",
            "public_highway": True, "encounter_on_undivided_approach": True,
            "opposing_lane_directions": [1, -1], "traffic_line_capacity_each_direction": [1, 1],
            "capacity_source": "map lane review", "paved_y_bounds_m": [-3.5, 3.5],
            "ego_half_width_m": 0.8, "other_half_width_m": 0.8,
            "cross_sections": rows,
            "verified_centers_y_m": {
                "right_half": {"ego": -1.7, "other": 1.7},
                "wrong_side": {"ego": 1.7, "other": -1.7},
                "left_encroachment": {"ego": -0.7, "other": 1.7},
                "right_constrained": {"ego": -1.5, "other": 1.7},
            },
            "physical_constraint": {"source_kind": "original_native_map_geometry",
                "source_id": "diagnostic-right-edge-feature",
                "station_range_m": [-4, 4], "lateral_range_m": [-3.5, -2.4]}}


def history(ego_y=-1.7, other_y=1.7):
    rows = []
    for i in range(3):
        rows.append({"frame": i, "time_s": i / 20, "ego_id": "ego", "other_id": "other",
                     "ego_speed_s_mps": 6, "other_speed_s_mps": -6,
                     "paved_y_bounds_m": [-3.5, 3.5],
                     "ego_body_s_bounds_m": [-1 + i, 1 + i],
                     "other_body_s_bounds_m": [1 - i, 3 - i],
                     "ego_body_y_bounds_m": [ego_y - 0.8, ego_y + 0.8],
                     "other_body_y_bounds_m": [other_y - 0.8, other_y + 0.8]})
    return {"source_kind": "original_native_actor_history",
            "map_source_kind": "original_native_map_geometry", "public_highway": True,
            "encounter_on_undivided_approach": True,
            "traffic_line_capacity_each_direction": [1, 1],
            "capacity_source": "map lane review", "paved_boundary_source": "map edge review",
            "actor_ids": ["ego", "other"], "samples": rows}


class SiteTests(unittest.TestCase):
    def test_source_road_frame_projects_opposing_routes(self):
        packet = site()
        packet["native_road_frame"] = {"source_id": "opendrive-waypoint-axis",
                                       "origin_xyz_m": [100, 50, 0.2], "forward_xy": [0, 1]}
        routes = module.world_routes(packet, "right_half")
        self.assertEqual(routes["ego_world_xyz_m"][0], [101.7, 25.0, 0.2])
        self.assertEqual(routes["other_world_xyz_m"][0], [98.3, 75.0, 0.2])
        packet["native_road_frame"]["forward_xy"] = [2, 0]
        with self.assertRaises(ValueError):
            module.world_routes(packet, "right_half")

    def test_native_pair_spawn_readback_and_cleanup(self):
        class Actor:
            def __init__(self, ident):
                self.id = ident
                self.destroyed = False
            def get_transform(self):
                return (self.id, "readback")
            def destroy(self):
                self.destroyed = True
        class Blueprints:
            def find(self, ident):
                return ident
        class World:
            def __init__(self, fail_second=False):
                self.created = []
                self.fail_second = fail_second
            def try_spawn_actor(self, blueprint, transform):
                if self.fail_second and len(self.created) == 1:
                    return None
                actor = Actor(len(self.created) + 1)
                self.created.append(actor)
                return actor
        packet = site()
        packet["native_spawn"] = {"right_half": {
            "ego": {"blueprint_id": "vehicle.a", "pose_xyz_ypr": [0, -1.7, 0, 0, 0, 0], "source_id": "ego-waypoint"},
            "other": {"blueprint_id": "vehicle.b", "pose_xyz_ypr": [30, 1.7, 0, 180, 0, 0], "source_id": "other-waypoint"}}}
        world = World()
        result = module.spawn_native_pair(world, Blueprints(), packet, "right_half", tuple)
        self.assertEqual(result["actor_ids"], [1, 2])
        self.assertEqual(result["route_request"]["other_heading_sign"], -1)
        failing = World(fail_second=True)
        with self.assertRaises(ValueError):
            module.spawn_native_pair(failing, Blueprints(), packet, "right_half", tuple)
        self.assertTrue(failing.created[0].destroyed)
        packet["native_spawn"]["right_half"]["ego"]["source_id"] = ""
        with self.assertRaises(ValueError):
            module.spawn_native_pair(World(), Blueprints(), packet, "right_half", tuple)

    def test_all_three_routes_construct_opposing_directions(self):
        for variant in module.VARIANTS:
            route = module.construct(site(), variant)
            self.assertEqual(route["ego_heading_sign"], 1)
            self.assertEqual(route["other_heading_sign"], -1)
            self.assertEqual(route["ego_route"][0][0], -25)
            self.assertEqual(route["other_route"][0][0], 25)

    def test_reject_divided_or_unsupported_width(self):
        for change in ({"encounter_on_undivided_approach": False},
                       {"traffic_line_capacity_each_direction": [2, 1]}):
            packet = site()
            packet.update(change)
            with self.assertRaises(ValueError):
                module.construct(packet, "right_half")

    def test_reject_overlap_and_unverified_map(self):
        packet = site()
        packet["verified_centers_y_m"]["left_encroachment"]["ego"] = 1
        with self.assertRaises(ValueError):
            module.construct(packet, "left_encroachment")
        packet = site()
        packet["cross_sections"][0]["source"] = "declared"
        with self.assertRaises(ValueError):
            module.construct(packet, "right_half")

    def test_right_constrained_requires_constructed_source_feature(self):
        packet = site()
        del packet["physical_constraint"]
        with self.assertRaisesRegex(ValueError, "source-recorded physical constraint"):
            module.construct(packet, "right_constrained")
        packet = site()
        packet["physical_constraint"]["lateral_range_m"] = [-3.5, -3.4]
        with self.assertRaisesRegex(ValueError, "too remote"):
            module.construct(packet, "right_constrained")

    def test_sealed_source_rejects_mutation(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "map.json"
            path.write_text(json.dumps(site()), encoding="utf-8")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(module.load_sealed(path, digest)["layout"], "median_opening")
            path.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                module.load_sealed(path, digest)


class MeasurementTests(unittest.TestCase):
    def test_saved_finalizer_requires_sealed_original_and_write_once(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "original.json"
            output = Path(tmp) / "measurement.json"
            source.write_text(json.dumps(history()), encoding="utf-8")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            document = module.finalize_sealed(source, digest, output)
            self.assertEqual(document["measurement"]["passing_frames"], [0, 1, 2])
            self.assertEqual(document["legal_judgment"], "unresolved")
            with self.assertRaises(FileExistsError):
                module.finalize_sealed(source, digest, output)
            source.write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                module.finalize_sealed(source, digest, Path(tmp) / "second.json")

    def test_half_and_encroachment_measured_without_legal_label(self):
        right = module.measure(history())
        encroached = module.measure(history(ego_y=-0.7))
        self.assertTrue(right["right_of_other_all"])
        self.assertLess(right["ego_north_edge_from_half_max_m"], 0)
        self.assertGreater(encroached["ego_north_edge_from_half_max_m"], 0)
        self.assertEqual(encroached["legal_judgment"], "unresolved")

    def test_wrong_side_and_missing_interval(self):
        self.assertFalse(module.measure(history(ego_y=1.7, other_y=-1.7))["right_of_other_all"])
        packet = history()
        for row in packet["samples"]:
            row["other_body_s_bounds_m"] = [10, 12]
        with self.assertRaises(ValueError):
            module.measure(packet)

    def test_stop_outside_pass_does_not_erase_measured_encounter(self):
        packet = history()
        packet["samples"].append({**packet["samples"][-1], "frame": 3,
            "time_s": .15, "ego_speed_s_mps": 0, "other_speed_s_mps": 0,
            "ego_body_s_bounds_m": [10, 12], "other_body_s_bounds_m": [-12, -10]})
        self.assertEqual(module.measure(packet)["passing_frames"], [0, 1, 2])
        packet["samples"][1]["ego_speed_s_mps"] = 0
        with self.assertRaisesRegex(ValueError, "during passing"):
            module.measure(packet)

    def test_reject_nonoriginal_gap_identity_and_transient(self):
        base = history()
        for patch in ({"source_kind": "synthetic"}, {"actor_ids": ["ego", "ego"]}):
            packet = copy.deepcopy(base)
            packet.update(patch)
            with self.assertRaises(ValueError):
                module.measure(packet)
        packet = history()
        packet["samples"][1]["frame"] = 3
        with self.assertRaises(ValueError):
            module.measure(packet)

    def test_comparison_rejects_missing_and_changed_fixed_conditions(self):
        base = {"source_kind": "original_native_actor_history", "map_sha256": "abc",
                "camera_profile": "four", "duration_s": 45,
                "actor_blueprints": ["car.a", "car.b"],
                "traffic_line_capacity_each_direction": [1, 1],
                "paved_boundary_source": "map", "passing_frames": [100],
                "measurements": {"right_of_other_all": True, "ego_north_edge_from_half_max_m": -0.3}}
        changed = copy.deepcopy(base)
        changed["measurements"]["ego_north_edge_from_half_max_m"] = 0.4
        module.audit_comparison(base, changed, "ego_north_edge_from_half_max_m")
        changed["map_sha256"] = "different"
        with self.assertRaises(ValueError):
            module.audit_comparison(base, changed, "ego_north_edge_from_half_max_m")
        changed = copy.deepcopy(base)
        del changed["paved_boundary_source"]
        with self.assertRaises(ValueError):
            module.audit_comparison(base, changed, "right_of_other_all")


if __name__ == "__main__":
    unittest.main()
