"""Small source-shaped tests; these rows are never an original Native run."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from delivery_audit import check_native_boundary, check_original_rows


class DeliveryAuditBoundaryTest(unittest.TestCase):
    def make_rows(self, folder, synthetic=False):
        sample = [
            {"time_s": i / 20, "native_frame": i + 100,
             "native_body_xy_m": [[-2, -3], [-2, -1], [2, -1], [2, -3]],
             "speed_mps": 0.0,
             "speed_provenance": "synthetic_native_sample" if synthetic else "native_velocity_readback"}
            for i in range(2)]
        values = {
            "trace.jsonl": [{"frame": s["native_frame"], "time_s": s["time_s"],
                             "speed_provenance": s["speed_provenance"]} for s in sample],
            "capture/evidence.jsonl": [
                {"original_frame": s["native_frame"], "recording_time_s": s["time_s"],
                 "ego": {"speed_provenance": s["speed_provenance"]}}
                for s in sample],
            "video_frames.jsonl": [
                {"native_frame": s["native_frame"], "carla_frame": s["native_frame"],
                 "video_frame": i, "time_s": s["time_s"]}
                for i, s in enumerate(sample)],
            "native_samples.jsonl": sample,
            "body_history.jsonl": [
                {"frame": s["native_frame"], "time_s": s["time_s"]}
                for s in sample],
        }
        for name, rows in values.items():
            target = folder / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("".join(json.dumps(row) + "\n" for row in rows))

    def test_source_join_and_synthetic_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            self.make_rows(folder)
            self.assertEqual(check_original_rows(folder, 2)["frames"], 2)
            self.make_rows(folder, synthetic=True)
            with self.assertRaisesRegex(ValueError, "Synthetic diagnostic"):
                check_original_rows(folder, 2)

    def test_missing_and_mismatched_native_rows_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            self.make_rows(folder)
            (folder / "native_samples.jsonl").unlink()
            with self.assertRaisesRegex(ValueError, "Missing original source"):
                check_original_rows(folder, 2)
            self.make_rows(folder)
            source = folder / "native_samples.jsonl"
            rows = [json.loads(line) for line in source.read_text().splitlines()]
            rows[1]["native_frame"] = 999
            source.write_text("".join(json.dumps(row) + "\n" for row in rows))
            with self.assertRaisesRegex(ValueError, "frame join"):
                check_original_rows(folder, 2)

    def test_unsealed_attempt_rejected_before_saved_result(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            with self.assertRaisesRegex(ValueError, "Missing sealed Native capture"):
                check_native_boundary(folder, folder, folder / "owner.json",
                                      "case", "0" * 64)


if __name__ == "__main__":
    unittest.main()
