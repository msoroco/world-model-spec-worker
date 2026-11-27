"""Focused CPU checks for source-gated private-way geometry and approaches."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
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
sys.path.insert(0, str(MODULE_PATH.parent))
from private_way_motion import measure
from native_acquisition import capture
from native_operator import _station
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
            "highway_axis_xy": [1, 0],
            "routes": {
                "enter": [[-8, 0], [0, 0], [5, 0]],
                "cross": [[-8, 0], [0, 0], [12, 0]],
            },
            "approaches": {
                "left": [[-1, -3], [0, 0], [2, 3]],
                "right": [[8, 2], [0, 0], [-1, -2]],
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

    def test_highway_route_passes_connection(self):
        for route in self.site["approaches"].values():
            at_connection = _station(self.site["connection_xy"], route)
            self.assertGreater(at_connection - _station(route[0], route), 0)
            self.assertLess(at_connection - _station(route[-1], route), 0)

    def _motion_fixture(self):
        self.site["case_id"] = construction.ASSIGNMENT + "__enter_both_wait"
        self.save()
        (self.root / "site.json").write_text(self.packet.read_text())
        rows = []
        for index in range(9):
            rows.append({
                "case_id": self.site["case_id"], "frame": index,
                "native_frame": 100 + index, "time_s": 5 + index / 20,
                "ego_on_highway": index >= 5,
                "ego_speed_mps": 0 if index < 5 else 3,
                "highway_vehicles": [
                    {"actor_id": "left-car", "side": "left",
                     "distance_to_connection_m": 12 - index, "speed_mps": 4},
                    {"actor_id": "right-car", "side": "right",
                     "distance_to_connection_m": 14 - index, "speed_mps": 4},
                ],
            })
        motion = self.root / "motion.jsonl"
        motion.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
        seal = {"format": "worker-private-way-motion-seal",
                "case_id": self.site["case_id"], "frame_count": 9,
                "diagnostic_fixture": True,
                "motion_sha256": hashlib.sha256(motion.read_bytes()).hexdigest(),
                "site_sha256": hashlib.sha256((self.root / "site.json").read_bytes()).hexdigest()}
        (self.root / "motion-seal.json").write_text(json.dumps(seal) + "\n")
        return rows

    def test_sealed_original_motion_and_missing_actor(self):
        rows = self._motion_fixture()
        observed = measure(self.root, self.site["case_id"])
        self.assertEqual(observed["first_highway_frame"], 5)
        self.assertEqual(set(observed["highway_actor_ids"]), {"left", "right"})
        self.assertFalse(observed["physical_acceptance_claimed"])
        rows[4]["highway_vehicles"].pop()
        motion = self.root / "motion.jsonl"
        motion.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
        seal_file = self.root / "motion-seal.json"
        seal = json.loads(seal_file.read_text())
        seal["motion_sha256"] = hashlib.sha256(motion.read_bytes()).hexdigest()
        seal_file.write_text(json.dumps(seal) + "\n")
        with self.assertRaisesRegex(ValueError, "actor missing"):
            measure(self.root, self.site["case_id"])

    def test_original_motion_hash_mismatch(self):
        self._motion_fixture()
        (self.root / "motion.jsonl").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "source hash differs"):
            measure(self.root, self.site["case_id"])

    def test_diagnostic_native_acquisition_and_release(self):
        self.site["case_id"] = construction.ASSIGNMENT + "__enter_both_wait"
        self.save()

        class FakeOperator:
            native_attested = False
            capture_cleanup_complete = False

            def __init__(self, packet):
                self.packet = packet
                self.index = -1

            def get_site_packet(self, case_id):
                return self.packet

            def get_opendrive_bytes(self):
                return (self.packet.parent / "native_opendrive_map.txt").read_bytes()

            def start(self, plan):
                self.plan = plan

            def read_actor_inventory(self):
                return {"ego_vehicle_id": "ego", "highway_vehicles":
                        {"left": "left-car", "right": "right-car"}}

            def tick(self):
                self.index += 1
                return {"frame": 100 + self.index, "time_s": 5 + self.index / 20}

            def read_motion(self, frame):
                return {"native_frame": frame, "case_id": self.plan["case_id"],
                        "source_kind": "original_native", "ego_vehicle_id": "ego",
                        "ego_on_highway": self.index >= 5,
                        "ego_speed_mps": 0 if self.index < 5 else 3,
                        "highway_vehicles": [
                            {"actor_id": "left-car", "side": "left",
                             "distance_to_connection_m": 12 - self.index,
                             "speed_mps": 4},
                            {"actor_id": "right-car", "side": "right",
                             "distance_to_connection_m": 14 - self.index,
                             "speed_mps": 4},
                        ]}

            def read_cameras(self, frame):
                return {name: {"frame": frame, "time_s": 5 + self.index / 20,
                               "png": b"\x89PNG\r\n\x1a\nsynthetic"}
                        for name in ("overview", "approach", "reference_corner",
                                     "driver_reference")}

            def brake(self):
                self.braked = True

            def cleanup(self):
                self.cleaned = True

            def encode_media(self, root, cameras, frames):
                for name in (*cameras, "raw"):
                    (root / (name + ".mkv")).write_bytes(b"synthetic fixture media")
                return {name: str(root / (name + ".mkv"))
                        for name in (*cameras, "raw")}

        fake = FakeOperator(self.packet)
        output = self.root / "attempt"
        observed = capture(fake, self.site["case_id"], output,
                           diagnostic_frames=9)
        self.assertTrue(fake.braked and fake.cleaned and fake.capture_cleanup_complete)
        self.assertEqual(observed["first_highway_frame"], 5)
        self.assertEqual(observed["highway_actor_ids"],
                         {"left": "left-car", "right": "right-car"})
        self.assertEqual(len(list((output / "site-sources").iterdir())), 6)
        self.assertEqual(site_module.load_site(output / "site.json",
                                               self.site["case_id"])["case_id"],
                         self.site["case_id"])
        self.assertTrue((output / "inventory.json").is_file())
        self.assertEqual(json.loads((output / "inventory.json").read_text())[
            "source_kind"], "synthetic_fixture")


if __name__ == "__main__":
    unittest.main()
