"""Exercise lossless projection from four sealed original camera archives."""
import hashlib
import io
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZIP_STORED, ZipFile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import native_seal
import saved_package


class NativeSealTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        image = Image.new("RGB", (8, 8), "yellow")
        packet = io.BytesIO()
        image.save(packet, format="PNG")
        events, aspects = [], []
        for i in range(900):
            events.append({"frame": i + 100, "ego_xy": [float(i) / 20, 0.0],
                           "ego_z_m": 0.5, "ego_speed_mps": 1.0,
                           "ego_brake": 0.0, "ego_heading_deg": 90.0,
                           "ego_body_vertices_m": [[float(i) / 20 + x, y, 0.5]
                                                   for x, y in ((0,0),(1,0),(1,1),(0,1))]})
            aspects.append({"frame": i + 100, "elapsed_seconds": i / 20})
        (self.root / "arrow-events-original.json").write_text(json.dumps(events))
        (self.root / "arrow-aspect-original.json").write_text(json.dumps(aspects))
        sources = {}
        for name in native_seal.CAMERAS:
            path = self.root / (name + ".png.zip")
            with ZipFile(path, "w", compression=ZIP_STORED) as archive:
                for i in range(900):
                    archive.writestr(f"{i+100:08d}.png", packet.getvalue())
            sources[name] = {"path": path.name,
                             "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        (self.root / "arrow-camera-receipt.json").write_text(json.dumps({
            "frame_count": 900, "camera_sources": sources}))

    def tearDown(self):
        self.temporary.cleanup()

    def test_four_original_archives_project_and_join(self):
        native_output = types.ModuleType("worker_exchange.native_output")
        native_output.seal_capture = lambda *args, **kwargs: {"sealed": True,
                                                                "frames": kwargs["frames"]}
        with patch.dict(sys.modules, {"worker_exchange": types.ModuleType("worker_exchange"),
                                      "worker_exchange.native_output": native_output}):
            result = native_seal.seal(self.root)
        self.assertEqual(result, {"sealed": True, "frames": 900})
        trace = [json.loads(s) for s in (self.root / "trace.jsonl").read_text().splitlines()]
        mapping = [json.loads(s) for s in (self.root / "video_frames.jsonl").read_text().splitlines()]
        self.assertEqual(len(trace), len(mapping))
        self.assertEqual(len(trace), 900)
        self.assertEqual(len((self.root / "body_history.jsonl").read_text().splitlines()), 900)
        self.assertEqual(trace[0]["frame"], mapping[0]["carla_frame"])
        for name in native_seal.CAMERAS:
            self.assertTrue((self.root / (name + ".mkv")).is_file())
            archive = self.root / (name + ".png.zip")
            receipt = json.loads((self.root / "arrow-camera-receipt.json").read_text())
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(),
                             receipt["camera_sources"][name]["sha256"])
        repo = ROOT.parents[1]
        pipeline_output = repo / ".runtime-work/c111610-nov24-owner/pipeline"
        pipeline_output.mkdir(parents=True, exist_ok=True)
        os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(pipeline_output)
        sys.path.insert(0, str(repo / "runtime/scenario_pipeline"))
        sys.path.insert(1, str(repo / "runtime/python"))
        construction = json.loads((ROOT / "construction-arrow_clear.json").read_text())
        (self.root / "construction.json").write_text(json.dumps(construction))
        (self.root / "config.json").write_text(json.dumps({
            "law_id": "NRS-484B-307-7a", "cell_id": "C111610",
            "selected_case_id": ROOT.name + "__arrow_clear", "case_suffix": "arrow_clear",
            "duration_s": 45, "rate_hz": 20,
            "physical_completion": {"criterion": "turn", "motion_source": "body_history.jsonl",
                                    "body_key": "body_vertices_m", "heading_key": "heading_deg",
                                    "turn_degrees": 90, "turn_tolerance_deg": 30,
                                    "minimum_progress_m": 1.0, "context_sources": []}}))
        (self.root / "site.json").write_text(json.dumps({
            "ego_route_xy": [[0,-8],[0,0],[-8,0]],
            "intersection_polygon_xy": [[-3,-3],[3,-3],[3,3],[-3,3]],
            "adjacent_crosswalk_polygon_xy": [[3,-3],[6,-3],[6,3],[3,3]],
            "native_map_name": "TownTest", "official_head_id": "17",
            "signal_source_path": "signal.json", "route_source_path": "route.json"}))
        events = json.loads((self.root / "arrow-events-original.json").read_text())
        for row in events:
            row["other_users"] = []
            row["ego_movement"] = "left"
        (self.root / "arrow-events-original.json").write_text(json.dumps(events))
        aspects = json.loads((self.root / "arrow-aspect-original.json").read_text())
        for row in aspects:
            row["concurrent_indications"] = []
        (self.root / "arrow-aspect-original.json").write_text(json.dumps(aspects))
        result = saved_package.build_result(self.root, {
            "measurements": {"arrow_display_observation": {"value": {"frame_count": 900}}},
            "source_inventory": {"site.json": "diagnostic-test"}})
        self.assertEqual(len(result["recording_evidence"]), 12)
        self.assertEqual(result["physical_checks"]["setup"]["status"], "met")
        self.assertFalse(result["maneuver_completed"])
        from batch_pipeline.validation import recording_evidence
        recording_evidence(result, construction["recording_description"],
                           lambda ref: self.root / ref)

    def test_changed_original_archive_rejected(self):
        archive = self.root / "overview.png.zip"
        archive.write_bytes(archive.read_bytes() + b"changed")
        native_output = types.ModuleType("worker_exchange.native_output")
        native_output.seal_capture = lambda *args, **kwargs: None
        with patch.dict(sys.modules, {"worker_exchange": types.ModuleType("worker_exchange"),
                                      "worker_exchange.native_output": native_output}):
            with self.assertRaisesRegex(ValueError, "original camera archive changed"):
                native_seal.seal(self.root)


if __name__ == "__main__":
    unittest.main()
