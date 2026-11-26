"""Focused source, hierarchy, timing and priority checks for Native capture."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

import native_signal as signal


class NativeSignalTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[2] / ".runtime-work" / "c24757-owner"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.site_path = self.root / "site.json"
        records = {}
        hashes = {}
        for name in signal.SOURCES:
            path = self.root / (name + ".source")
            path.write_text("reviewed " + name + "\n")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            records[name] = {"path": path.name, "sha256": digest}
            hashes[name + "_source_sha256"] = digest
        self.site = {
            "source_kind": "reviewed_original_native_signal_site",
            "assignment_id": signal.ASSIGNMENT,
            "case_id": signal.ASSIGNMENT + "__line_prior_stop_yield",
            "source_records": records,
            "entrance_ids": ["north", "east"],
            "governing_head_ids": ["head-n1", "head-n2", "head-e1"],
            "signal_id": "signal-reviewed", "governed_approach": "north",
            "driver_id": "driver-reviewed", "ego_vehicle_id": "ego-reviewed",
            "other_vehicle_id": "other-reviewed", "road_id": 4, "lane_id": -1,
            "through_highway_id": "through-reviewed", "signal_installed": True,
            "vehicular_heads_uncovered": True,
            "complete_inoperability_at_entry": True,
            "signal_governs_approach": True,
            "through_highway_reviewed": True, "sightline_reviewed": True,
            "blind_intersection_reviewed": True, "physical_occluder_reviewed": True,
            "intersection_entry_m": 22.0, "stop_line_m": 18.0,
            "near_crosswalk_m": 19.0, "nearest_view_point_m": 20.0,
            "other_state": "prior_stop", "ego_policy": "yield",
            "ego_route_station_m": [0.0, 30.0],
            "other_route_station_m": [0.0, 30.0],
            **hashes,
        }
        self.case = signal.CASES[0]

    def rows(self):
        ego, other = [], []
        hashes = {name + "_source_sha256": self.site[name + "_source_sha256"]
                  for name in signal.SOURCES}
        for i in range(9):
            ego.append({"original_frame": 100 + i, "time_s": i * .05,
                        "vehicle_id": "ego-reviewed", "signal_id": "signal-reviewed",
                        "approach_id": "north", "front_m": [10, 12, 14, 16, 17, 17, 18, 22, 23][i],
                        "speed_mps": 0 if i == 5 else 2,
                        "signal_installed": True, "signal_uncovered": True,
                        "signal_operating": False,
                        "governing_head_operating": {
                            "head-n1": False, "head-n2": False, "head-e1": False},
                        "all_heads_wholly_inoperative": True, **hashes})
            other.append({"original_frame": 100 + i, "time_s": i * .05,
                          "vehicle_id": "other-reviewed", "signal_id": "signal-reviewed",
                          "front_m": float(i), "speed_mps": 0 if i == 2 else 2,
                          "within_intersection": False,
                          "cleared_conflict_zone": i >= 6, **hashes})
        return ego, other

    def test_original_stop_and_prior_vehicle(self):
        ego, other = self.rows()
        result = signal.measure_original(self.site, self.site_path, self.case,
                                         ego, other, diagnostic=True)
        self.assertEqual(result["stop_original_frame"], 105)
        self.assertEqual(result["entry_original_frame"], 107)
        self.assertTrue(result["priority_vehicle_observed"])
        self.assertTrue(result["yield_sequence_observed"])
        self.assertIsNone(result["legal_judgment"])

    def test_source_change_rejected(self):
        (self.root / "signal_operation.source").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "source bytes changed"):
            signal.validate_site(self.site, self.site_path, self.case)

    def test_blind_occluder_source_required(self):
        self.site["physical_occluder_reviewed"] = False
        with self.assertRaisesRegex(ValueError, "occluder"):
            signal.validate_site(self.site, self.site_path, self.case)

    def test_enter_before_priority_clearance_measured(self):
        case = signal.CASES[2]
        self.site["case_id"] = signal.ASSIGNMENT + "__" + case.name
        self.site["ego_policy"] = "enter"
        ego, other = self.rows()
        for i, row in enumerate(other):
            row["cleared_conflict_zone"] = i >= 8
        measured = signal.measure_original(self.site, self.site_path, case,
                                           ego, other, diagnostic=True)
        self.assertFalse(measured["yield_sequence_observed"])
        self.assertIsNone(measured["legal_judgment"])

    def test_crosswalk_requires_absent_line(self):
        crosswalk = signal.CASES[4]
        self.site["case_id"] = signal.ASSIGNMENT + "__" + crosswalk.name
        with self.assertRaisesRegex(ValueError, "hierarchy"):
            signal.validate_site(self.site, self.site_path, crosswalk)
        self.site["stop_line_m"] = None
        self.assertEqual(signal.validate_site(self.site, self.site_path, crosswalk), 19.0)

    def test_entry_operation_and_frame_join_rejected(self):
        ego, other = self.rows()
        ego[7]["signal_operating"] = True
        with self.assertRaisesRegex(ValueError, "inoperative signal"):
            signal.measure_original(self.site, self.site_path, self.case,
                                    ego, other, diagnostic=True)
        ego[7]["signal_operating"] = False
        other[3]["original_frame"] += 1
        with self.assertRaisesRegex(ValueError, "frame join"):
            signal.measure_original(self.site, self.site_path, self.case,
                                    ego, other, diagnostic=True)

    def test_one_governing_head_operating_at_entry_rejected(self):
        ego, other = self.rows()
        ego[7]["governing_head_operating"]["head-e1"] = True
        ego[7]["all_heads_wholly_inoperative"] = False
        with self.assertRaisesRegex(ValueError, "inoperative signal"):
            signal.measure_original(self.site, self.site_path, self.case,
                                    ego, other, diagnostic=True)


if __name__ == "__main__":
    unittest.main()
