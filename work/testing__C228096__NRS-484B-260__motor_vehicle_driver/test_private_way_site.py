"""Focused CPU checks for source-gated private-way geometry and approaches."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest


MODULE_PATH = Path(__file__).with_name("private_way_site.py")
spec = importlib.util.spec_from_file_location("private_way_site", MODULE_PATH)
site_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site_module)
construction_spec = importlib.util.spec_from_file_location(
    "private_way_construction", MODULE_PATH.with_name("private_way_construction.py"))
construction = importlib.util.module_from_spec(construction_spec)
construction_spec.loader.exec_module(construction)
CASE = "testing__C228096__NRS-484B-260__motor_vehicle_driver__enter_right_wait"


class PrivateWaySiteTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        sources = {}
        for name in site_module.REQUIRED_SOURCES:
            file = self.root / (name + ".txt")
            file.write_text("reviewed source for " + name + "\n")
            sources[name] = {
                "path": file.name,
                "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
            }
        self.site = {
            "format": "worker-private-way-site-v1",
            "case_id": CASE,
            "sources": sources,
            "reviewed_assertions": {
                "private_ownership": True,
                "restricted_public_access": True,
                "destination_public_highway": True,
                "permitted_vehicular_use": True,
                "feasible_connection": True,
            },
            "private_way_polygon": [[-10, -2], [-3, -2], [-3, 2], [-10, 2]],
            "highway_polygon": [[-2, -4], [10, -4], [10, 4], [-2, 4]],
            "connection_xy": [0, 0],
            "routes": {
                "enter": [[-8, 0], [0, 0], [5, 0]],
                "cross": [[-8, 0], [0, 0], [12, 0]],
            },
            "approaches": {
                "left": [[-1, -3], [-0.5, -1], [0, 0]],
                "right": [[8, 2], [4, 1], [0, 0]],
            },
        }
        self.packet = self.root / "site.json"
        self.save()

    def save(self):
        self.packet.write_text(json.dumps(self.site) + "\n")

    def test_source_checked_entry_and_crossing(self):
        loaded = site_module.load_site(self.packet, CASE)
        self.assertEqual(set(loaded["routes"]), {"enter", "cross"})

    def test_missing_original_source_rejected(self):
        (self.root / "boundary_map.txt").unlink()
        with self.assertRaisesRegex(ValueError, "missing original site source"):
            site_module.load_site(self.packet, CASE)

    def test_changed_original_source_rejected(self):
        (self.root / "boundary_map.txt").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "source hash mismatch"):
            site_module.load_site(self.packet, CASE)

    def test_missing_private_status_rejected(self):
        self.site["reviewed_assertions"]["private_ownership"] = False
        self.save()
        with self.assertRaisesRegex(ValueError, "private_ownership"):
            site_module.load_site(self.packet, CASE)

    def test_wrong_approach_direction_rejected(self):
        self.site["approaches"]["right"].reverse()
        self.save()
        with self.assertRaisesRegex(ValueError, "not directed"):
            site_module.load_site(self.packet, CASE)

    def test_both_approaching_actors_required(self):
        history = [
            {"frame": 100, "time_s": 5.0, "highway_vehicles": [
                {"actor_id": "a", "side": "left", "distance_to_connection_m": 10},
                {"actor_id": "b", "side": "right", "distance_to_connection_m": 12}]},
            {"frame": 101, "time_s": 5.05, "highway_vehicles": [
                {"actor_id": "a", "side": "left", "distance_to_connection_m": 9},
                {"actor_id": "b", "side": "right", "distance_to_connection_m": 11}]},
        ]
        result = site_module.assess_approaching(history, ["left", "right"])
        self.assertEqual(result["actor_ids"], ["a", "b"])
        self.assertEqual(result["legal_yield_judgment"], "unresolved")
        del history[1]["highway_vehicles"][1]
        with self.assertRaisesRegex(ValueError, "approaching vehicle source missing"):
            site_module.assess_approaching(history, ["left", "right"])

    def test_all_nine_exact_targets_are_constructed(self):
        for variant, (maneuver, sides, policy) in construction.CASES.items():
            self.site["case_id"] = construction.ASSIGNMENT + "__" + variant
            target = construction.build_plan(self.site, self.site["case_id"])
            self.assertEqual(target["maneuver"], maneuver)
            self.assertEqual(set(target["highway_approach_routes_xy_m"]), set(sides))
            self.assertEqual(target["requested_control_policy"], policy)
            self.assertEqual(target["capture"]["frames"], 900)
            self.assertEqual(target["legal_yield_judgment"], "unresolved")

    def test_spawn_fallback_keeps_case_and_policy(self):
        self.site["case_id"] = construction.ASSIGNMENT + "__enter_both_wait"
        base = construction.build_plan(self.site, self.site["case_id"])
        fallback = construction.build_plan(self.site, self.site["case_id"],
                                           spawn_offset_m=3.0)
        self.assertEqual(base["requested_control_policy"],
                         fallback["requested_control_policy"])
        self.assertEqual(base["ego_route_xy_m"], fallback["ego_route_xy_m"])
        self.assertNotEqual(base["highway_approach_routes_xy_m"],
                            fallback["highway_approach_routes_xy_m"])
        with self.assertRaisesRegex(ValueError, "spawn offset"):
            construction.build_plan(self.site, self.site["case_id"],
                                    spawn_offset_m=8.0)


if __name__ == "__main__":
    unittest.main()
