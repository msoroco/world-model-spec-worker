import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_uturn import SourceError, analyze_native


CASE = "testing__C111706__NRS-484B-403-3__motor_vehicle_driver__intersection_vehicle_near"


def packet():
    frames = []
    for i, yaw in enumerate((0.0, 90.0, 180.0)):
        frames.append({"frame": 100 + i, "time_s": i * .05,
                       "ego": {"id": "ego", "road_id": 7, "lane_id": 1 if i < 2 else -1,
                               "junction_id": 4 if i == 1 else None, "x": float(i), "y": 0.0,
                               "yaw_deg": yaw,
                               "body_corners_xy_m": [[float(i)-.1,-.1],[float(i)+.1,-.1],
                                                     [float(i)+.1,.1],[float(i)-.1,.1]]},
                       "other_vehicle": {"id": "other", "road_id": 7, "lane_id": -1,
                                         "x": 5.0, "y": 0.0}})
    return {"case_id": CASE, "actor": "motor_vehicle_driver", "map_sha256": "map-seal",
            "route_sha256": "route-seal", "district_basis": {"source_sha256": "district-seal"},
            "intersection_boundary": {"source_sha256": "boundary-seal",
                                      "polygon_xy_m": [[.5,-1],[1.5,-1],[1.5,1],[.5,1]]},
            "ego_id": "ego", "other_id": "other", "frames": frames}


class NativeUTurnTest(unittest.TestCase):
    def check(self, value):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "native.json"
            p.write_text(json.dumps(value), encoding="utf-8")
            seal = hashlib.sha256(p.read_bytes()).hexdigest()
            return analyze_native(p, expected_case=CASE, expected_sha256=seal)

    def test_intersection_and_reversal(self):
        result = self.check(packet())
        self.assertTrue(result["junction_occupied_during_reversal"])
        self.assertEqual(result["whole_body_inside_intersection_frames"], [101])
        self.assertEqual(result["reversal_deg"], 180)
        self.assertEqual(result["district_classification"], "unresolved_review")

    def test_outside_intersection_is_measured_not_assumed(self):
        value = packet()
        for sample in value["frames"]:
            sample["ego"]["junction_id"] = None
        self.assertFalse(self.check(value)["junction_occupied_during_reversal"])

    def test_rejects_noncontiguous_original_frames(self):
        value = packet()
        value["frames"][1]["frame"] += 5
        with self.assertRaisesRegex(SourceError, "noncontiguous"):
            self.check(value)

    def test_rejects_missing_participant(self):
        value = packet()
        del value["frames"][1]["other_vehicle"]
        with self.assertRaisesRegex(SourceError, "other vehicle source"):
            self.check(value)

    def test_rejects_false_reversal(self):
        value = packet()
        value["frames"][-1]["ego"]["yaw_deg"] = 30
        with self.assertRaisesRegex(SourceError, "full reversal"):
            self.check(value)

    def test_rejects_stale_source_seal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "native.json"
            path.write_text(json.dumps(packet()), encoding="utf-8")
            with self.assertRaisesRegex(SourceError, "hash mismatch"):
                analyze_native(path, expected_case=CASE, expected_sha256="0" * 64)

    def test_rejects_duplicate_time(self):
        value = packet()
        value["frames"][1]["time_s"] = 0.0
        with self.assertRaisesRegex(SourceError, "time sequence"):
            self.check(value)

    def test_body_footprint_required(self):
        value = packet()
        del value["frames"][1]["ego"]["body_corners_xy_m"]
        with self.assertRaisesRegex(SourceError, "body footprint missing"):
            self.check(value)
