"""Source-bound original capture protocol checks with CPU-only Native fakes."""

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from projection_capture import CAMERAS, FRAMES, capture_original
from analysis import analyze
from projection_sources import load_reviewed
from test_projection_construction import FakeAdapter, SITE


class CaptureAdapter(FakeAdapter):
    def __init__(self):
        super().__init__()
        self.current = 100
        self.restored = False
        self.camera_path = None
        self.fail_camera = False

    def pipeline_client(self):
        return self

    def start_cameras(self, output, plan):
        self.camera_path = Path(output)
        self.calls.append("start_cameras")

    def hold_parked_assembly(self, built, index):
        self.calls.append("hold")

    def tick_world(self):
        frame = self.current
        self.current += 1
        return frame, (frame - 100) / 20

    def camera_frame_ids(self, frame):
        if self.fail_camera:
            return {name: frame for name in CAMERAS[:-1]}
        return {name: frame for name in CAMERAS}

    def sample_parked_assembly(self, built, frame):
        return {"physical_parts": built["physical_parts"],
                "curb_segment_start_m": SITE["curb_segment_start_m"],
                "curb_segment_end_m": SITE["curb_segment_end_m"],
                "street_side_reference_m": SITE["street_side_reference_m"],
                "vehicle_station_m": built["station_m"]}

    def trace_identity(self):
        return "cpu-fake-trace"

    def finish_cameras(self):
        paths = {}
        for name in CAMERAS:
            path = self.camera_path / (name + ".mkv")
            path.write_bytes(b"fixture camera bytes")
            paths[name] = path
        return paths

    def abort_cameras(self):
        self.calls.append("abort_cameras")

    def restore_world(self):
        self.restored = True
        return True


class Pipeline:
    def __init__(self, client, actor, out, case_id, required_observations):
        self.out = Path(out)
        self.closed = False
        self.stream = (self.out / "trace.jsonl").open("w", encoding="utf-8")

    def capture(self, frame, elapsed):
        self.stream.write(json.dumps({"frame": frame, "time_s": elapsed}) + "\n")
        return {"frame": frame, "time_s": elapsed}

    def close(self, confirmed):
        self.stream.close()
        self.closed = True


def seal_fake(out, **kwargs):
    (Path(out) / "capture-seal.json").write_text(json.dumps(kwargs) + "\n", encoding="utf-8")


def packet_in(root, case_id):
    source_names = ["opendrive", "curb_survey", "vehicle_dimensions",
                    "load_dimensions", "trailer_dimensions"]
    sources = {}
    for name in source_names:
        path = root / (name + ".txt")
        path.write_text(name + " reviewed original fixture\n", encoding="utf-8")
        sources[name] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                         "citation": name + " fixture", "reviewer": "source review fixture"}
    site = dict(SITE, opendrive_sha256=sources["opendrive"]["sha256"])
    plan = {name: {"source_transform": "reviewed pose fixture", "purpose": "assembly visibility"}
            for name in CAMERAS}
    packet = {"format": "c150088-original-site-v1", "assignment_id": case_id.rsplit("__", 1)[0],
              "reviewer": "source review fixture", "review_citation": "CPU test only",
              "site": site, "sources": sources, "camera_plan": plan}
    path = root / "site-packet.json"
    path.write_text(json.dumps(packet) + "\n", encoding="utf-8")
    return path


class CaptureTest(unittest.TestCase):
    def test_reviewed_source_byte_mutation_rejected(self):
        Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as temp:
            root = Path(temp)
            case = "testing__C150088__LVMC-11-52-060__motor_vehicle_driver__vehicle_below"
            packet = packet_in(root, case)
            (root / "curb_survey.txt").write_text("changed after review\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source byte binding differs"):
                load_reviewed(packet, case)

    def test_original_frame_join_and_cleanup(self):
        Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as temp:
            root = Path(temp)
            case = "testing__C150088__LVMC-11-52-060__motor_vehicle_driver__vehicle_below"
            packet = packet_in(root, case)
            adapter = CaptureAdapter()
            # The fake adapter validates the reviewed site map hash dynamically.
            adapter.verify_loaded_map = lambda digest: digest == json.loads(packet.read_text())["site"]["opendrive_sha256"]
            result = capture_original(adapter, packet, case, root / "attempt",
                                      pipeline_factory=Pipeline, seal_factory=seal_fake)
            self.assertEqual(result["frames"], FRAMES)
            self.assertTrue(adapter.restored)
            self.assertEqual(adapter.actors, {})
            self.assertEqual(len((root / "attempt" / "video_frames.jsonl").read_text().splitlines()), FRAMES)
            self.assertEqual(len((root / "attempt" / "original-projection-history.jsonl").read_text().splitlines()), FRAMES)
            (root / "attempt" / "capture-seal.json").unlink()
            (root / "attempt" / "config.json").write_text(json.dumps({
                "assignment_id": case.rsplit("__", 1)[0], "selected_case_id": case,
                "case": {"case_id": case, "recording_description": {"channels": [
                    {"name": name, "unit": "CPU fixture"} for name in (
                        "maximum_perpendicular_projection", "controlling_physical_part",
                        "curb_street_side_geometry", "parked_assembly_stability",
                        "camera_frame_identity")], "context_inputs": [
                    {"name": "reviewed_original_opendrive_and_curb_survey", "unit": "source hashes"},
                    {"name": "vehicle_load_trailer_attachment", "unit": "source actor IDs"}]}}}) + "\n")
            (root / "attempt" / "diagnostic-source-note.json").write_text(json.dumps({
                "source_kind": "synthetic_diagnostic_fixture", "accepted_original_source": False,
                "case_id": case}) + "\n")
            report = analyze(root / "attempt")
            self.assertTrue(report["diagnostic_fixture"])
            self.assertAlmostEqual(report["measurements"]["maximum_perpendicular_projection"]["value"]["maximum_m"], 4.2)
            self.assertFalse(report["target_check"]["legal_equality_claimed"])

    def test_missing_camera_join_is_rejected_and_world_restored(self):
        Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as temp:
            root = Path(temp)
            case = "testing__C150088__LVMC-11-52-060__motor_vehicle_driver__vehicle_below"
            packet = packet_in(root, case)
            adapter = CaptureAdapter()
            adapter.verify_loaded_map = lambda digest: digest == json.loads(packet.read_text())["site"]["opendrive_sha256"]
            adapter.fail_camera = True
            with self.assertRaisesRegex(ValueError, "four original cameras"):
                capture_original(adapter, packet, case, root / "attempt",
                                 pipeline_factory=Pipeline, seal_factory=seal_fake)
            self.assertTrue(adapter.restored)
            self.assertEqual(adapter.actors, {})
            self.assertIn("abort_cameras", adapter.calls)


if __name__ == "__main__":
    unittest.main()
