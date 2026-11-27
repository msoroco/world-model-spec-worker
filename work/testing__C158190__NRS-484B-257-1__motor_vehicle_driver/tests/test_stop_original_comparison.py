"""Synthetic 900-frame contract probes; no original Native evidence is claimed."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stop_sign_branch import ASSIGNMENT, CASES
from stop_view_measurement import compare_original, inspect_original, SOURCE_KEYS


def packet(case_id, stop_frames):
    site = {key: "a" * 64 for key in SOURCE_KEYS}
    site.update({"source_kind": "original_native_readback", "cell_id": "C158190",
                 "control": "stop_sign", "planned_response": CASES[case_id],
                 "stop_line_present": False, "near_crosswalk_present": False,
                 "sidewalk_derived_crosswalk_present": False, "police_control_active": False,
                 "traffic_signal_control_active": False, "camera_plan_sha256": "b" * 64,
                 "intersection_id": "synthetic-intersection", "ego_route_id": "synthetic-route",
                 "duration_frames": 900,
                 "approach_view_stations": [
                     {"station_id": "far", "distance_to_intersection_m": 5,
                      "view_of_through_traffic": True},
                     {"station_id": "nearest", "distance_to_intersection_m": 2,
                      "view_of_through_traffic": True}]})
    rows = []
    for i in range(900):
        crossing = 100 <= i <= 130
        rows.append({"frame": i, "time_s": i / 20,
                     "ego_speed_mps": 0.0 if 100 - stop_frames <= i < 100 else 2.0,
                     "ego_within_intersection": crossing,
                     "distance_to_intersection_m": 2.0 if i < 100 else 0.0,
                     "through_vehicles": [{"id": "synthetic-through", "through_highway": True,
                                           "distance_to_conflict_m": 10 - i / 20,
                                           "speed_mps": 4.0}]})
    return {"assignment_id": ASSIGNMENT, "case_id": case_id,
            "original_trace_id": "synthetic-contract-probe", "site": site, "frames": rows}


class ComparisonContractTests(unittest.TestCase):
    def test_exact_pair_and_fixed_stop_source(self):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as tmp:
            root = Path(tmp)
            ids = list(CASES)
            left, right = root / "left.json", root / "right.json"
            left.write_text(json.dumps(packet(ids[0], 40)) + "\n")
            right.write_text(json.dumps(packet(ids[1], 5)) + "\n")
            result = compare_original(left, right)
            self.assertEqual(result["variable"], "ego_response")
            self.assertEqual(len(result["measurements"]), 2)
            self.assertEqual(len(inspect_original(left, ids[0])["pre_entry_stop_frame_indices"]), 40)
            altered = json.loads(right.read_text())
            altered["site"]["map_source_sha256"] = "c" * 64
            right.write_text(json.dumps(altered) + "\n")
            with self.assertRaisesRegex(ValueError, "fixed stop-response source differs"):
                compare_original(left, right)

    def test_wrong_governing_control_rejected(self):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as tmp:
            case = next(iter(CASES))
            value = packet(case, 5)
            value["site"]["control"] = "yield_sign"
            path = Path(tmp) / "wrong-control.json"
            path.write_text(json.dumps(value) + "\n")
            with self.assertRaisesRegex(ValueError, "fixed C158190 stop governance"):
                inspect_original(path, case)


if __name__ == "__main__":
    unittest.main()
