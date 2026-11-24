"""Exercise seven source-bound accepted-reuse pairs with diagnostic originals."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comparison_audit import audit
from sight_measurement import DIRECTIONS, STATIONS_M


HERE = Path(__file__).resolve().parents[1]
PLAN = json.loads((HERE / "case-plan.json").read_text())


class ComparisonAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=".runtime-work")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def attempt(self, name, case_id, recording_id, location, blocked_direction=None,
                blocked_stations=()):
        root = self.root / name
        root.mkdir()
        frames = [{"frame": i, "time_s": i / 20} for i in range(900)]
        motion = [dict(row, yaw_deg=(0 if i < 100 else 180),
                       turn_active=i in (100, 101)) for i, row in enumerate(frames)]
        motion[100]["yaw_deg"] = 0
        rays = []
        for row in frames[100:102]:
            for direction in DIRECTIONS:
                for station in STATIONS_M:
                    occluded = direction == blocked_direction and station in blocked_stations
                    rays.append({"frame": row["frame"], "time_s": row["time_s"],
                                 "direction": direction, "station_distance_m": station,
                                 "observer_height_m": 1.4,
                                 "observer_lane_source": "diagnostic lane source",
                                 "target_vehicle_id": "ego-1",
                                 "body_point_clear": [not occluded] * 9,
                                 "terrain_hit_id": "diagnostic terrain" if occluded else None})
        packets = {
            "frame_map": {"frames": frames},
            "ego_motion": {"case_id": case_id, "source_kind": "original_native", "samples": motion},
            "sight_rays": {"case_id": case_id, "source_kind": "original_native", "samples": rays},
            "road_geometry": {"source_kind": "original_native_geometry",
                              "highway_source": "diagnostic map source", "location_kind": location,
                              "ego_vehicle_id": "ego-1"},
        }
        inventory = {"case_id": case_id, "recording_id": recording_id,
                     "source_kind": "original_native", "sources": {}}
        for key, value in packets.items():
            path = root / (key + ".json")
            path.write_text(json.dumps(value) + "\n")
            inventory["sources"][key] = {"path": path.name,
                                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        return root, inventory

    def make_pair(self, pair):
        kind = pair["case_ids"][0].split("__")[-1]
        location = ("approach_to_crest" if kind.startswith("approach_to_crest") else
                    "near_crest" if kind.startswith("near_crest") else "curve")
        direction = ("behind_same_direction" if pair["comparison_id"].endswith("behind_same_direction")
                     else "ahead_opposing")
        first = self.attempt("left", pair["case_ids"][0], pair["recording_ids"][0], location,
                             "ahead_opposing" if pair["comparison_id"] == "discontinuous_reversal" else None,
                             (50.0,) if pair["comparison_id"] == "discontinuous_reversal" else ())
        second = self.attempt("right", pair["case_ids"][1], pair["recording_ids"][1], location,
                              direction, (100.0,))
        return first, second

    def test_all_seven_declared_pairs(self):
        for pair in PLAN["accepted_comparisons_pending_original_review"]:
            with self.subTest(pair=pair["comparison_id"]):
                (left_root, left_inv), (right_root, right_inv) = self.make_pair(pair)
                result = audit(PLAN, pair["comparison_id"], left_root, left_inv,
                               right_root, right_inv)
                self.assertEqual(result["recording_ids"], pair["recording_ids"])
                self.assertEqual(result["driver_visibility_judgment"], "unresolved")
                self.assertEqual(result["accepted_reuse_review"], "pending_original_video_and_context_review")
                for root in (left_root, right_root):
                    for file in root.iterdir():
                        file.unlink()
                    root.rmdir()

    def test_wrong_recording_and_fixed_geometry_rejected(self):
        pair = PLAN["accepted_comparisons_pending_original_review"][0]
        (left_root, left_inv), (right_root, right_inv) = self.make_pair(pair)
        right_inv["recording_id"] = "wrong"
        with self.assertRaisesRegex(ValueError, "recording identity"):
            audit(PLAN, pair["comparison_id"], left_root, left_inv, right_root, right_inv)
        right_inv["recording_id"] = pair["recording_ids"][1]
        path = right_root / "road_geometry.json"
        data = json.loads(path.read_text()); data["highway_source"] = "different map"
        path.write_text(json.dumps(data) + "\n")
        right_inv["sources"]["road_geometry"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "fixed road geometry"):
            audit(PLAN, pair["comparison_id"], left_root, left_inv, right_root, right_inv)

    def test_missing_measured_difference_rejected(self):
        pair = PLAN["accepted_comparisons_pending_original_review"][0]
        (left_root, left_inv), (right_root, right_inv) = self.make_pair(pair)
        path = right_root / "sight_rays.json"
        data = json.loads(path.read_text())
        for row in data["samples"]:
            row["body_point_clear"] = [True] * 9
            row["terrain_hit_id"] = None
        path.write_text(json.dumps(data) + "\n")
        right_inv["sources"]["sight_rays"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "declared sight difference absent"):
            audit(PLAN, pair["comparison_id"], left_root, left_inv, right_root, right_inv)


if __name__ == "__main__":
    unittest.main()
