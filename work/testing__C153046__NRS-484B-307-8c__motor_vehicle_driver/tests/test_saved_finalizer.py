"""Check saved canonical result and recording streams without CARLA."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from saved_measurement import finalize_attempt
from tests.test_saved_measurement import protocol


def attempt(root, *, suffix="stopped_leftmost_clear"):
    site, trace, case_id, rows = protocol(root, suffix=suffix)
    for row in rows:
        row["frame"] = row["native_frame"]["frame"]
        row["distance_to_stop_boundary_m"] = 1.0
        row["speed_mps"] = row["native_frame"]["ego"]["velocity_xyz_mps"][1]
        row["requested_phase"] = "stopping"
        row["control_request"] = {"throttle": 0.0, "brake": 1.0, "steer": 0.0}
        row["junction_exited"] = False
    trace.write_text("".join(json.dumps(row) + "\n" for row in rows))
    (root / "config.json").write_text(json.dumps({"selected_case_id": case_id,
        "law_id": "NRS-484B-307-8c", "cell_id": "C153046",
        "case": {"case_id": case_id}}))
    (root / "video_frames.jsonl").write_text("".join(json.dumps({
        "video_frame": index, "carla_frame": row["frame"], "time_s": row["time_s"]}) + "\n"
        for index, row in enumerate(rows)))
    for name in ("overview", "approach", "reference_corner", "driver_reference"):
        (root / (name + ".mkv")).write_bytes(b"synthetic media placeholder")
    return case_id


class SavedFinalizerTests(unittest.TestCase):
    def test_canonical_fields_and_source_preservation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case_id = attempt(root)
            original = (root / "trace.jsonl").read_bytes()
            report = finalize_attempt(root, root / "analysis-report.json")
            result = json.loads((root / "result.json").read_text())
            self.assertEqual(report["case_id"], case_id)
            self.assertEqual(report["measurements"]["stationary_duration_before_boundary_s"]["method"], "measure")
            self.assertEqual(set(report["measurements"]["engineering_stop_observed"]["sources"]),
                             {"site.json", "trace.jsonl"})
            self.assertEqual((root / "trace.jsonl").read_bytes(), original)
            self.assertEqual(len(result["recording_evidence"]), 10)
            self.assertFalse(result["setup_confirmed"])
            self.assertFalse(result["maneuver_completed"])
            self.assertEqual(result["trace_reference"], "trace.jsonl")
            stream = root / result["recording_evidence"][0]["reference"]
            self.assertEqual(len(stream.read_text().splitlines()), 13)
            with self.assertRaisesRegex(ValueError, "retain previous"):
                finalize_attempt(root, root / "analysis-report.json")

    def test_missing_media_and_wrong_frame_map_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            attempt(root)
            (root / "driver_reference.mkv").unlink()
            with self.assertRaisesRegex(ValueError, "four-view media"):
                finalize_attempt(root, root / "analysis-report.json")
            self.assertFalse((root / "channels").exists())
            (root / "driver_reference.mkv").write_bytes(b"synthetic media placeholder")
            mapping = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
            mapping[1]["carla_frame"] = 99
            (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in mapping))
            with self.assertRaisesRegex(ValueError, "frame map differs"):
                finalize_attempt(root, root / "analysis-report.json")


if __name__ == "__main__":
    unittest.main()
