import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from door_measurement import ASSIGNMENT, measure
from comparison_audit import audit_pair


class DoorMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = Path(__file__).resolve().parents[1] / "case-plan.json"
        self.case = ASSIGNMENT + "__cargo_active"
        frames = [{"frame": i + 100, "time_s": i / 20} for i in range(60)]
        self.packets = {
            "frame_map": {"frames": frames},
            "door": {"case_id": self.case, "source_kind": "original_native",
                     "vehicle_id": "selected-1",
                     "samples": [dict(row, open=10 <= i < 40, side="left")
                                 for i, row in enumerate(frames)]},
            "activity": {"case_id": self.case, "source_kind": "original_native",
                         "vehicle_id": "selected-1",
                         "samples": [dict(row, active=10 <= i < 40, kind="cargo")
                                     for i, row in enumerate(frames)]},
            "passing_vehicle": {
                "case_id": self.case, "source_kind": "original_native",
                "samples": [dict(row, vehicle_id="other-1", center_x_m=-8 + i * .3,
                                 center_y_m=2.2, width_m=1.5, length_m=4.0)
                            for i, row in enumerate(frames)]},
            "geometry": {"source_kind": "original_native_geometry",
                         "road_width_m": 6.0,
                         "selected_vehicle_center_y_m": 0.0,
                         "selected_vehicle_center_x_m": 0.0,
                         "selected_vehicle_width_m": 2.0,
                         "selected_vehicle_length_m": 4.0,
                         "selected_vehicle_id": "selected-1",
                         "passing_vehicle_id": "other-1",
                         "loading_position_supported": True},
        }
        self.inventory = self.seal()

    def seal(self):
        inventory = {"case_id": self.case, "source_kind": "original_native", "sources": {}}
        for name, payload in self.packets.items():
            path = self.root / (name + ".json")
            path.write_text(json.dumps(payload))
            inventory["sources"][name] = {"path": path.name,
                                           "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        (self.root / "inventory.json").write_text(json.dumps(inventory))
        return inventory

    def test_traffic_side_cargo_measurement_has_no_legal_verdict(self):
        result = measure(self.root, self.inventory, self.case, self.plan)
        self.assertEqual(result["open_start_frame"], 110)
        self.assertEqual(result["closed_after_frame"], 140)
        self.assertAlmostEqual(result["open_duration_s"], 1.5)
        self.assertEqual(result["inactive_open_duration_s"], 0)
        self.assertTrue(result["door_closest_to_passing_traffic"])
        self.assertEqual(result["legal_necessity_or_immediacy"], "unresolved")

    def test_inactive_open_interval_is_measured(self):
        self.case = ASSIGNMENT + "__cargo_inactive"
        for name in ("door", "activity", "passing_vehicle"):
            self.packets[name]["case_id"] = self.case
        for row in self.packets["activity"]["samples"][25:40]:
            row["active"] = False
        self.inventory = self.seal()
        result = measure(self.root, self.inventory, self.case, self.plan)
        self.assertAlmostEqual(result["inactive_open_duration_s"], .75)

    def test_passenger_and_opposite_side_cases(self):
        self.case = ASSIGNMENT + "__passenger_active"
        for name in ("door", "activity", "passing_vehicle"):
            self.packets[name]["case_id"] = self.case
        for row in self.packets["activity"]["samples"]:
            row["kind"] = "passenger"
        self.inventory = self.seal()
        self.assertEqual(measure(self.root, self.inventory, self.case, self.plan)["activity_kind"],
                         "passenger")
        self.case = ASSIGNMENT + "__opposite_side_control"
        for name in ("door", "activity", "passing_vehicle"):
            self.packets[name]["case_id"] = self.case
        for row in self.packets["activity"]["samples"]:
            row["kind"] = "cargo"
        for row in self.packets["door"]["samples"]:
            row["side"] = "right"
        self.inventory = self.seal()
        self.assertFalse(measure(self.root, self.inventory, self.case, self.plan)[
            "door_closest_to_passing_traffic"])

    def test_rejects_tampered_source_and_join_gap(self):
        (self.root / "door.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            measure(self.root, self.inventory, self.case, self.plan)
        self.packets["door"]["samples"][20]["frame"] += 1
        self.inventory = self.seal()
        with self.assertRaisesRegex(ValueError, "frame/time join"):
            measure(self.root, self.inventory, self.case, self.plan)

    def test_rejects_missing_loading_or_closure(self):
        for row in self.packets["activity"]["samples"]:
            row["active"] = False
        self.inventory = self.seal()
        with self.assertRaisesRegex(ValueError, "no original loading activity"):
            measure(self.root, self.inventory, self.case, self.plan)
        self.packets["activity"]["samples"][10]["active"] = True
        self.packets["door"]["samples"][-1]["open"] = True
        self.inventory = self.seal()
        with self.assertRaisesRegex(ValueError, "opening and closing"):
            measure(self.root, self.inventory, self.case, self.plan)

    def test_rejects_wrong_traffic_side_or_same_vehicle(self):
        self.packets["passing_vehicle"]["samples"][0]["center_y_m"] = -2.2
        self.inventory = self.seal()
        with self.assertRaisesRegex(ValueError, "traffic side changes"):
            measure(self.root, self.inventory, self.case, self.plan)
        self.packets["passing_vehicle"]["samples"][0]["center_y_m"] = 2.2
        self.packets["geometry"]["passing_vehicle_id"] = "selected-1"
        self.inventory = self.seal()
        with self.assertRaisesRegex(ValueError, "separate"):
            measure(self.root, self.inventory, self.case, self.plan)

    def test_rejects_stationary_vehicle_as_passing(self):
        for row in self.packets["passing_vehicle"]["samples"]:
            row["center_x_m"] = -8
        self.inventory = self.seal()
        with self.assertRaisesRegex(ValueError, "door-window traversal"):
            measure(self.root, self.inventory, self.case, self.plan)

    def test_rejects_wrong_selected_vehicle_source_and_offroad_passing_body(self):
        self.packets["door"]["vehicle_id"] = "other-1"
        self.inventory = self.seal()
        with self.assertRaisesRegex(ValueError, "source identity"):
            measure(self.root, self.inventory, self.case, self.plan)
        self.packets["door"]["vehicle_id"] = "selected-1"
        self.packets["passing_vehicle"]["samples"][0]["center_y_m"] = 3.0
        self.inventory = self.seal()
        with self.assertRaisesRegex(ValueError, "outside original road"):
            measure(self.root, self.inventory, self.case, self.plan)

    def test_source_bound_comparison_checks_fixed_path_and_difference(self):
        left = self.root / "left"
        right = self.root / "right"
        left.mkdir()
        right.mkdir()
        def write_attempt(root, packets, case_id):
            inventory = {"case_id": case_id, "source_kind": "original_native",
                         "sources": {}}
            for name, packet in packets.items():
                path = root / (name + ".json")
                path.write_text(json.dumps(packet))
                inventory["sources"][name] = {
                    "path": path.name,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            (root / "inventory.json").write_text(json.dumps(inventory))
        write_attempt(left, self.packets, self.case)
        other_case = ASSIGNMENT + "__cargo_inactive"
        other = copy.deepcopy(self.packets)
        for name in ("door", "activity", "passing_vehicle"):
            other[name]["case_id"] = other_case
        for row in other["activity"]["samples"][25:40]:
            row["active"] = False
        write_attempt(right, other, other_case)
        receipt = audit_pair(left, right, "cargo_activity_gap", self.plan)
        self.assertTrue(receipt["fixed_original_sources_reopened"])
        self.assertEqual(receipt["legal_necessity_or_immediacy"], "unresolved")
        other["passing_vehicle"]["samples"][30]["center_x_m"] += .2
        write_attempt(right, other, other_case)
        with self.assertRaisesRegex(ValueError, "passing vehicle path differs"):
            audit_pair(left, right, "cargo_activity_gap", self.plan)

    def test_other_three_controlled_comparisons(self):
        left = self.root / "left"
        right = self.root / "right"
        left.mkdir()
        right.mkdir()
        def write(root, packets, case_id):
            inventory = {"case_id": case_id, "source_kind": "original_native",
                         "sources": {}}
            for name, packet in packets.items():
                path = root / (name + ".json")
                path.write_text(json.dumps(packet))
                inventory["sources"][name] = {
                    "path": path.name,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            (root / "inventory.json").write_text(json.dumps(inventory))
        for comparison, left_suffix, right_suffix in (
                ("passenger_activity_gap", "passenger_active", "passenger_inactive"),
                ("door_side", "cargo_active", "opposite_side_control"),
                ("load_kind", "cargo_active", "passenger_active")):
            a = copy.deepcopy(self.packets)
            b = copy.deepcopy(self.packets)
            left_case = ASSIGNMENT + "__" + left_suffix
            right_case = ASSIGNMENT + "__" + right_suffix
            for name in ("door", "activity", "passing_vehicle"):
                a[name]["case_id"] = left_case
                b[name]["case_id"] = right_case
            if left_suffix.startswith("passenger"):
                for row in a["activity"]["samples"]:
                    row["kind"] = "passenger"
            if right_suffix.startswith("passenger"):
                for row in b["activity"]["samples"]:
                    row["kind"] = "passenger"
            if right_suffix.endswith("inactive"):
                for row in b["activity"]["samples"][25:40]:
                    row["active"] = False
            if right_suffix == "opposite_side_control":
                for row in b["door"]["samples"]:
                    row["side"] = "right"
            write(left, a, left_case)
            write(right, b, right_case)
            receipt = audit_pair(left, right, comparison, self.plan)
            self.assertTrue(receipt["deliberate_differences_measured"])


if __name__ == "__main__":
    unittest.main()
