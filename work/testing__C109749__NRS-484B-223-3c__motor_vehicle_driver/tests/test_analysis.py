"""Diagnostic saved sources and production camera boundary for selected analysis."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import analysis
import native_capture
from test_native_capture import site


class AnalysisTests(unittest.TestCase):
    def make_attempt(self, case_id):
        self.temporary = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        attempt = root / "original-attempt"
        attempt.mkdir()
        packet = site(attempt)
        camera_root = attempt / "camera"
        camera_root.mkdir()
        source = camera_root / "pixel.png"
        source.write_bytes(b"diagnostic camera placeholder")
        rows = []
        for index in range(900):
            frame = 1000 + index
            merged = index == 899 and not case_id.endswith("__no_merge")
            rows.append({
                "frame": frame, "elapsed_seconds": index / 20,
                "body_centre_xy_m": [index * 0.0166, 0.0],
                "lane_id": "approach" if index == 0 else
                           ("east" if merged else "center"),
                "approach_lane": index == 0,
                "left_turn_onto_highway_complete": index == 1,
                "merged_into_through_lane": merged,
                "camera_sources": {view: "camera/pixel.png" for view in native_capture.VIEWS},
            })
        native_capture.capture_original(attempt, case_id, packet, rows.__getitem__, 900,
                                        first_frame=1000)
        frame_map_path = attempt / "native/frame_map.json"
        frame_map = json.loads(frame_map_path.read_text())
        for row in frame_map["frames"]:
            del row["camera_sha256"]
        frame_map_path.write_text(json.dumps(frame_map) + "\n")
        receipt_path = attempt / "native/capture-receipt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["frame_map_source"]["sha256"] = hashlib.sha256(frame_map_path.read_bytes()).hexdigest()
        receipt_path.write_text(json.dumps(receipt) + "\n")
        source.unlink()
        (root / "fixture-provenance.json").write_text('{"diagnostic_fixture": true}\n')
        return root

    def test_selected_merge_and_censored_diagnostic(self):
        for suffix in ("below_50ft", "no_merge"):
            with self.subTest(suffix=suffix):
                case = HERE.name + "__" + suffix
                root = self.make_attempt(case)
                report = analysis.finalize(root, case)
                self.assertEqual(report["case_id"], case)
                self.assertEqual(report["measurements"]["observed_turn_and_merge"]["value"]["censored"],
                                 suffix == "no_merge")
                self.assertIsNone(report["legal_judgment"])

    def test_missing_case_source_fails_and_production_needs_original_pixels(self):
        case = HERE.name + "__below_50ft"
        root = self.make_attempt(case)
        (root / "original-attempt/native/site-packet.json").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source"):
            analysis.finalize(root, case)
        root = self.make_attempt(case)
        (root / "fixture-provenance.json").unlink()
        with self.assertRaisesRegex(ValueError, "incomplete original four-camera source map"):
            analysis.finalize(root, case)

    def test_selected_cli_writes_recording_channels_and_native_result(self):
        case = HERE.name + "__below_50ft"
        root = self.make_attempt(case)
        construction = json.loads((HERE / "cases/below_50ft/construction.json").read_text())
        config = next(json.loads(item["content"]) for item in construction["files"]
                      if item["path"] == "config.json")
        (root / "config.json").write_text(json.dumps(config) + "\n")
        original = json.loads((root / "original-attempt/native/trace.json").read_text())["samples"]
        trace = [{"frame": row["frame"], "time_s": index / 20,
                  "position": {"x": row["body_centre_xy_m"][0],
                               "y": row["body_centre_xy_m"][1], "z": 0},
                  "position_m": [*row["body_centre_xy_m"], 0],
                  "heading_deg": 0, "speed_mps": 0} for index, row in enumerate(original)]
        mapping = [{"video_frame": index, "carla_frame": row["frame"], "time_s": index / 20}
                   for index, row in enumerate(original)]
        (root / "trace.jsonl").write_text("".join(json.dumps(row) + "\n" for row in trace))
        (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in mapping))
        sys.path.insert(0, str(HERE.parents[1] / "runtime/scenario_pipeline"))
        with patch.object(sys, "argv", ["analysis.py", "--attempt", str(root),
                                        "--output", str(root / "analysis-report.json")]):
            analysis.main()
        result = json.loads((root / "result.json").read_text())
        self.assertEqual(len(result["recording_evidence"]), 9)
        self.assertEqual(result["case_id"], case)
        self.assertFalse(result["physical_acceptance_claimed"])


if __name__ == "__main__":
    unittest.main()
