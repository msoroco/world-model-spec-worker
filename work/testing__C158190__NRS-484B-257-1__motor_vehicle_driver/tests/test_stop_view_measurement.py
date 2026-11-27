"""CPU checks for a candidate original stop-sign motion measurement."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("c158190_stop_view_measurement", ROOT / "stop_view_measurement.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class StopViewMeasurementTest(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd() / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="c158190-stop-measure-", dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.response = MODULE.ASSIGNMENT + "__stop_nearest_view_response"
        self.uninterrupted = MODULE.ASSIGNMENT + "__stop_nearest_view_uninterrupted"
        self.packet = self.make_packet(self.response)
        self.path = self.directory / "original.json"
        self.save()

    def make_packet(self, case_id):
        site = {
            "source_kind": "original_native_readback", "cell_id": "C158190",
            "control": "stop_sign", "planned_response": MODULE.CASES[case_id],
            "stop_line_present": False, "near_crosswalk_present": False,
            "sidewalk_derived_crosswalk_present": False,
            "police_control_active": False, "traffic_signal_control_active": False,
            "camera_plan_sha256": "c" * 64, "intersection_id": "intersection-1",
            "ego_route_id": "one-way-ego", "duration_frames": 900,
            "approach_view_stations": [
                {"station_id": "far", "distance_to_intersection_m": 12, "view_of_through_traffic": True},
                {"station_id": "near", "distance_to_intersection_m": 3, "view_of_through_traffic": True},
            ],
        }
        site.update({key: str(i) * 64 for i, key in enumerate(MODULE.SOURCE_KEYS)})
        frames = []
        for index in range(900):
            frames.append({"frame": index, "time_s": index / 20,
                           "ego_speed_mps": 0.0 if index == 100 else 2.0,
                           "distance_to_intersection_m": max(0.0, 8.0 - index * 0.05),
                           "ego_within_intersection": 200 <= index <= 300,
                           "through_vehicles": [{"id": "through-1", "through_highway": True,
                                                 "distance_to_conflict_m": 20 - index / 20,
                                                 "speed_mps": 4.0}]})
        return {"assignment_id": MODULE.ASSIGNMENT, "case_id": case_id,
                "original_trace_id": "diagnostic-source-shaped-only", "site": site, "frames": frames}

    def save(self):
        self.path.write_text(json.dumps(self.packet, sort_keys=True) + "\n")

    def test_stop_and_complete_crossing_measured(self):
        result = MODULE.inspect_original(self.path, self.response)
        self.assertEqual(result["pre_entry_stop_frame_indices"], [100])
        self.assertEqual(result["nearest_sampled_visible_station_id"], "near")
        self.assertEqual(result["crossing_frame_indices"], [200, 300])
        self.assertEqual(result["through_vehicle_motion"][0]["observed_crossing_frames"], 101)

    def test_missing_stop_and_gap_rejected(self):
        self.packet["frames"][100]["ego_speed_mps"] = 2.0
        self.save()
        with self.assertRaisesRegex(ValueError, "pre-entry stop"):
            MODULE.inspect_original(self.path, self.response)
        self.packet["frames"][100]["ego_speed_mps"] = 0.0
        self.packet["frames"][250]["ego_within_intersection"] = False
        self.save()
        with self.assertRaisesRegex(ValueError, "contiguous original crossing"):
            MODULE.inspect_original(self.path, self.response)

    def test_yield_control_and_missing_through_history_rejected(self):
        self.packet["site"]["control"] = "yield_sign"
        self.save()
        with self.assertRaisesRegex(ValueError, "fixed C158190 stop governance"):
            MODULE.inspect_original(self.path, self.response)
        self.packet["site"]["control"] = "stop_sign"
        self.packet["frames"][250].pop("through_vehicles")
        self.save()
        with self.assertRaisesRegex(ValueError, "through-highway history"):
            MODULE.inspect_original(self.path, self.response)

    def test_stop_must_be_at_sampled_view_station_and_through_traffic_present(self):
        self.packet["frames"][100]["distance_to_intersection_m"] = 8.0
        self.save()
        with self.assertRaisesRegex(ValueError, "pre-entry stop"):
            MODULE.inspect_original(self.path, self.response)
        self.packet["frames"][100]["distance_to_intersection_m"] = 3.0
        self.packet["frames"][250]["through_vehicles"] = []
        self.save()
        with self.assertRaisesRegex(ValueError, "participant missing during crossing"):
            MODULE.inspect_original(self.path, self.response)

    def test_exact_pair_and_fixed_sources(self):
        second = self.directory / "second.json"
        packet = self.make_packet(self.uninterrupted)
        second.write_text(json.dumps(packet, sort_keys=True) + "\n")
        result = MODULE.compare_original(self.path, second)
        self.assertEqual(result["variable"], "ego_response")
        packet["site"]["map_source_sha256"] = "f" * 64
        second.write_text(json.dumps(packet, sort_keys=True) + "\n")
        with self.assertRaisesRegex(ValueError, "fixed stop-response source differs"):
            MODULE.compare_original(self.path, second)


if __name__ == "__main__":
    unittest.main()
