"""Saved-only positive and missing-source checks for original passing evidence."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from analysis import analyze


HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        construction = json.loads((HERE / "construction-selected-bike_clearance_above.json").read_text())
        config_text = next(x["content"] for x in construction["files"]
                           if x["path"] == "config.json")
        (self.root / "config.json").write_text(config_text, encoding="utf-8")
        case_id = json.loads(config_text)["selected_case_id"]
        context = {"case_id": case_id, "highway_source": "reviewed site",
                   "lane_count_same_direction": 1, "centerline_y": 3,
                   "right_side_y": 1, "vehicle_id": "ego", "bicycle_id": "bike",
                   "bicycle_kind": "bicycle", "reviewed_packet_sha256": "fixture-packet"}
        write(self.root / "original-context.json", context)
        bike = [10, 12, 0, .5]
        boxes = [[0, 4, 0, .5], [9, 11, 1.7, 3.7], [13, 15, 1.5, 3.5]]
        rows = [{"origin": "native_world_snapshot", "frame": i,
                 "time_s": i * .05, "vehicle_box": box, "bicycle_box": bike,
                 "vehicle_speed_mps": 5, "bicycle_speed_mps": 2,
                 "vehicle_source": "motion", "bicycle_source": "motion",
                 "lane_source": "map", "opposing_traffic_source": "traffic"}
                for i, box in enumerate(boxes)]
        (self.root / "original-trace.jsonl").write_text(
            "".join(json.dumps(x) + "\n" for x in rows), encoding="utf-8")
        (self.root / "trace.jsonl").write_text("".join(json.dumps({
            "frame": row["frame"], "time_s": row["time_s"],
            "position_m": [(row["vehicle_box"][0] + row["vehicle_box"][1]) / 2,
                           (row["vehicle_box"][2] + row["vehicle_box"][3]) / 2]
        }) + "\n" for row in rows), encoding="utf-8")
        (self.root / "video_frames.jsonl").write_text("".join(json.dumps({
            "video_frame": i, "carla_frame": i, "native_frame": i,
            "time_s": i * .05}) + "\n" for i in range(3)), encoding="utf-8")
        write(self.root / "original-source-receipt.json", {
            "case_id": case_id, "source_kind": "synthetic_diagnostic_fixture",
            "diagnostic_fixture": True, "fps": 20, "frame_count": 3,
            "context_sha256": sha(self.root / "original-context.json"),
            "trace_sha256": sha(self.root / "original-trace.jsonl"),
            "reviewed_packet_sha256": "fixture-packet"})

    def test_saved_analysis_has_no_legal_claim(self):
        report = analyze(self.root)
        self.assertTrue(report["analysis_complete"])
        self.assertFalse(report["physical_acceptance_claimed"])
        self.assertTrue(report["measurements"]["pass_geometry"]["value"]
                        ["three_foot_floor_observed"])
        native = json.loads((self.root / "result.json").read_text())
        self.assertFalse(native["legal_verdict_claimed"])

    def test_missing_original_trace_rejected(self):
        (self.root / "original-trace.jsonl").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source"):
            analyze(self.root)

    def test_changed_original_trace_rejected(self):
        with (self.root / "original-trace.jsonl").open("a") as stream:
            stream.write("{}\n")
        with self.assertRaisesRegex(ValueError, "source changed"):
            analyze(self.root)


if __name__ == "__main__":
    unittest.main()
