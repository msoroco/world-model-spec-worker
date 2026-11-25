import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from saved_finalizer import finalize, validate_saved
from test_intersection_yield_measure import fixture


def saved_fixture(root):
    fixture(root)
    config = json.loads((ROOT / "config.json").read_text())
    config["selected_case_id"] = (
        "testing__C158196__NRS-484B-257-2__motor_vehicle_driver__signal_off_stop_signed_duty")
    (root / "config.json").write_text(json.dumps(config) + "\n")
    rows = [json.loads(line) for line in (root / "crossing_history.jsonl").read_text().splitlines()]
    (root / "trace.jsonl").write_text("".join(json.dumps({"frame": row["frame"],
        "time_s": row["time_s"]}) + "\n" for row in rows))
    (root / "capture").mkdir(exist_ok=True)
    (root / "capture/evidence.jsonl").write_text("".join(json.dumps({
        "original_frame": row["frame"]}) + "\n" for row in rows))
    for camera in ("overview", "approach", "reference_corner", "driver_reference"):
        (root / (camera + ".mkv")).write_text("fixture placeholder; real decoder checks media\n")


class SavedFinalizerTests(unittest.TestCase):
    def test_saved_only_finalization_preserves_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            saved_fixture(root)
            source_before = {name: (root / name).read_bytes() for name in (
                "entrance_inventory.json", "crossing_history.jsonl", "video_frames.jsonl",
                "trace.jsonl", "capture/evidence.jsonl")}
            analysis = finalize(root, root / "analysis.json")
            self.assertEqual(analysis["legal_conclusion"], "unresolved")
            self.assertEqual(len(list((root / "channels").glob("*.jsonl"))), 8)
            result = json.loads((root / "result.json").read_text())
            self.assertEqual(result["provenance_kind"], "synthetic_fixture")
            self.assertFalse(result["physical_acceptance_claimed"])
            self.assertFalse(result["setup_confirmed"])
            self.assertEqual(result["case_id"], analysis["case_id"])
            for name, content in source_before.items():
                self.assertEqual((root / name).read_bytes(), content)
            with self.assertRaisesRegex(ValueError, "fresh attempt"):
                finalize(root, root / "analysis-2.json")

    def test_exact_original_source_join_and_negative_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            saved_fixture(root)
            config, report, rows, frames, hashes = validate_saved(root)
            self.assertEqual(report["first_ego_entry_frame"], 102)
            self.assertEqual(len(rows), len(frames))
            self.assertEqual(len(hashes), 10)
            self.assertTrue(config["selected_case_id"].endswith("signal_off_stop_signed_duty"))
            trace = [json.loads(line) for line in (root / "trace.jsonl").read_text().splitlines()]
            trace[2]["frame"] = 999
            (root / "trace.jsonl").write_text("".join(json.dumps(row) + "\n" for row in trace))
            with self.assertRaisesRegex(ValueError, "frame join"):
                validate_saved(root)
            saved_fixture(root)
            (root / "overview.mkv").unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source"):
                validate_saved(root)


if __name__ == "__main__":
    unittest.main()
