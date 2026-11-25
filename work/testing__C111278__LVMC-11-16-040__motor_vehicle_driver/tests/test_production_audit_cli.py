import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from comparison_audit import ASSIGNMENT, main as comparison_main
from delivery_audit import DeliveryError, main as delivery_main


class ProductionAuditCliTests(unittest.TestCase):
    def test_delivery_cli_binds_attempt_processing_and_frame_source(self):
        case = ASSIGNMENT + "__blocked_at"
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / ".runtime-work" / "cli"
            attempt, processed = base / "attempt", base / "processed"
            attempt.mkdir(parents=True)
            processed.mkdir()
            frames = [{"frame": i, "time_s": i / 20} for i in range(900)]
            (attempt / "native-sight.json").write_text(json.dumps({
                "frames": frames, "entering_arms": ["west", "north", "east"]}) + "\n")
            (attempt / "native-sight-receipt.json").write_text(json.dumps({
                "map_hash": "a" * 64, "recorded_only": True,
                "capture_kind": "original_native", "fps": 20, "duration_s": 45}) + "\n")
            (attempt / "video_frames.jsonl").write_text("".join(json.dumps({
                "carla_frame": i, "time_s": i / 20}) + "\n" for i in range(900)))
            (attempt / "actor-census.jsonl").write_text("".join(json.dumps({
                "frame": i, "entering_arms": ["west", "north", "east"],
                "actors": []}) + "\n" for i in range(900)))
            (attempt / "analysis-report.json").write_text(json.dumps({
                "case_id": case, "analysis_complete": True,
                "diagnostic_fixture": False}) + "\n")
            (attempt / "result.json").write_text(json.dumps({
                "case_id": case, "diagnostic_fixture": False}) + "\n")
            for name in ("overview", "approach", "reference_corner", "driver_reference"):
                (attempt / (name + ".mkv")).write_bytes(name.encode())
            originals = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in attempt.iterdir() if path.is_file()}
            (processed / "processing.json").write_text(json.dumps({
                "case_id": case, "passed": True, "recorded_only": True,
                "originals_preserved": True, "missing_evidence": False,
                "candidate_id": "primary", "original_source_hashes": originals,
                "result_sha256": originals["result.json"]}) + "\n")
            measured = {"case_id": case, "map_hash": "a" * 64,
                        "approach_frame_ids": [100], "traversal_frame_ids": [200],
                        "source_sha256": {"original": "b" * 64}}
            output = base / "delivery-audit.json"
            with patch("delivery_audit.verify_saved", return_value={
                    "measurement": measured, "camera_capture": {"camera_frames": 900}}), \
                    patch("delivery_audit._decode_video", return_value={"decoded_frames": 900}):
                delivery_main(["--case", case, "--attempt", str(attempt),
                               "--processed", str(processed), "--output", str(output)])
                self.assertTrue(json.loads(output.read_text())["source_join_passed"])
                output.unlink()
                lines = (attempt / "video_frames.jsonl").read_text().splitlines()
                lines[100] = json.dumps({"carla_frame": 999, "time_s": 5.0})
                (attempt / "video_frames.jsonl").write_text("\n".join(lines) + "\n")
                with self.assertRaisesRegex(DeliveryError, "video frame map differs"):
                    delivery_main(["--case", case, "--attempt", str(attempt),
                                   "--processed", str(processed), "--output", str(output)])

    def test_comparison_cli_order_and_original_source(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / ".runtime-work" / "cli"
            base.mkdir(parents=True)
            first, second = base / "blocked_at", base / "clear_at"
            first.mkdir()
            second.mkdir()
            output = base / "comparison.json"
            values = {
                "blocked_at": {"case_id": ASSIGNMENT + "__blocked_at",
                               "map_hash": "a" * 64, "approach_frame_ids": [1],
                               "traversal_frame_ids": [2], "blocked_rays": [[1, "west", "traffic_view"]],
                               "through_designation": False, "traffic_controlled": False,
                               "traversal_speed_min_mps": 6.7,
                               "traversal_speed_max_mps": 6.7,
                               "source_sha256": {"site_source_sha256": "b" * 64,
                                                 "boundary_source_sha256": "c" * 64}},
                "clear_at": {"case_id": ASSIGNMENT + "__clear_at",
                             "map_hash": "a" * 64, "approach_frame_ids": [1],
                             "traversal_frame_ids": [2], "blocked_rays": [],
                             "through_designation": False, "traffic_controlled": False,
                             "traversal_speed_min_mps": 6.7,
                             "traversal_speed_max_mps": 6.7,
                             "source_sha256": {"site_source_sha256": "b" * 64,
                                               "boundary_source_sha256": "c" * 64}}}
            def verified(path, case):
                suffix = Path(path).name
                return {"case_id": case, "measurement": values[suffix],
                        "camera_capture": {"camera_frames": 900,
                                           "camera_images_decoded": 3600}}
            with patch("comparison_audit.verify", side_effect=verified):
                comparison_main(["--comparison", "sight_condition",
                                 "--attempt", str(first), "--attempt", str(second),
                                 "--output", str(output)])
                self.assertTrue(json.loads(output.read_text())["source_join_passed"])
                output.unlink()
                with self.assertRaises(ValueError):
                    comparison_main(["--comparison", "sight_condition",
                                     "--attempt", str(second), "--attempt", str(first),
                                     "--output", str(output)])


if __name__ == "__main__":
    unittest.main()
