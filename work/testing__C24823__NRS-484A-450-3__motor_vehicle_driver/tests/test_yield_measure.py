import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from yield_measure import measure
from yield_site import ASSIGNMENT


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class YieldMeasureTests(unittest.TestCase):
    def make(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        case = ASSIGNMENT + "__fallback_nearest_view_stop"
        site = {"assignment_id": ASSIGNMENT, "case_id": case, "map_id": "diagnostic-map",
                "control": "yield_sign", "yield_sign_id": "diagnostic-yield",
                "vehicle_type": "motor_vehicle", "ego_actor_id": "diagnostic-ego",
                "intersecting_highway_id": "diagnostic-highway", "approach_roadway_id": "diagnostic-approach",
                "stopping_required_for_safety": "unresolved", "source_review_status": "diagnostic_only",
                "nearest_crosswalk_position": None, "marked_stop_line_position": None,
                "intersecting_highway_boundary_x": 0, "approaching_traffic_points": [[2, 6]],
                "occluders": [[-4, 1, -3, 3]], "driver_viewpoint_candidates": [
                    {"id": "far", "position": [-6, 0]}, {"id": "near", "position": [-1, 0]}]}
        (root / "original-yield-site.json").write_text(json.dumps(site) + "\n")
        rows = [{"frame": 100+i, "time_s": i*.05, "ego_actor_id": "diagnostic-ego",
                 "ego_center_xy_m": [-2+i*.5, 0], "ego_speed_mps": 0 if i == 2 else 2,
                 "ego_vertices": [[-2+i*.5+dx,dy,z] for z in (-.4,.4)
                     for dx in (-.4,.4) for dy in (-.4,.4)],
                 "yield_control_readback": {"control": "yield_sign", "yield_sign_id": "diagnostic-yield"},
                 "camera_frames": {"overview": {"frame": 100+i}}} for i in range(4)]
        (root / "original-yield-trace.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rows))
        receipt = {"case_id": case, "frame_count": 4, "ego_actor_id": "diagnostic-ego",
                   "diagnostic_fixture": True,
                   "site_sha256": sha(root / "original-yield-site.json"),
                   "trace_sha256": sha(root / "original-yield-trace.jsonl")}
        (root / "original-yield-receipt.json").write_text(json.dumps(receipt) + "\n")
        return root, case

    def test_original_sources_and_stop_sample(self):
        root, case = self.make()
        result = measure(root, case)
        self.assertEqual(result["reference"]["selected_candidate_id"], "near")
        self.assertEqual(result["original_sample_count"], 4)
        self.assertEqual(len(result["original_stop_samples"]), 1)
        self.assertIsNone(result["legal_judgment"])

    def test_missing_original_trace_rejected(self):
        root, case = self.make()
        (root / "original-yield-trace.jsonl").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source"):
            measure(root, case)

    def test_changed_source_rejected(self):
        root, case = self.make()
        with (root / "original-yield-site.json").open("a") as stream:
            stream.write(" ")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            measure(root, case)


if __name__ == "__main__":
    unittest.main()
