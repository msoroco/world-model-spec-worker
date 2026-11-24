"""Exercise original-frame publication and fail-closed sealing with small RGB fixtures."""
from __future__ import annotations

import io
import json
import pathlib
import sys
import tempfile
import unittest
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[3]
BASE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
from finalize_capture import VIEWS, publish


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


class FinalizeCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".runtime-work")
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        original = self.root / "original-attempt"
        original.mkdir()
        (self.root / "runner.py").write_text("# diagnostic runner\n")
        (self.root / "construction.json").write_text("{}\n")
        (original / "attempt.json").write_text(json.dumps({
            "case_id": "exact-test-case", "acquisition_kind": "original_native"}) + "\n")
        (original / "map-source.json").write_text("{}\n")
        pose = [{"frame": i, "world_frame": 101 + i,
                 "time_s": i / 20, "x_m": 25.0 - i / 100,
                 "y_m": 0, "heading_deg": 180, "speed_mps": 0.0}
                for i in range(900)]
        write_rows(original / "pose.jsonl", pose)
        write_rows(original / "frame-map.jsonl", [
            {"frame": i, "world_frame": 101 + i, "time_s": i / 20}
            for i in range(900)])
        png = io.BytesIO()
        Image.new("RGB", (2, 2), (17, 39, 61)).save(png, format="PNG")
        for name in VIEWS:
            folder = original / "cameras" / name
            folder.mkdir(parents=True)
            for i in range(900):
                (folder / f"{i:06d}.png").write_bytes(png.getvalue())

    def test_complete_original_source_publishes_and_seals(self):
        report = publish(self.root, case_id="exact-test-case",
                         restoration={"restored": True})
        self.assertEqual(report["frame_count"], 900)
        self.assertTrue((self.root / "capture-seal.json").is_file())
        for name in VIEWS:
            self.assertTrue((self.root / (name + ".mkv")).is_file())
        trace = [json.loads(line) for line in (self.root / "trace.jsonl").read_text().splitlines()]
        self.assertEqual(len(trace), 900)
        self.assertEqual(trace[0]["frame"], 101)
        self.assertEqual(trace[-1]["frame"], 1000)

    def test_missing_original_camera_frame_prevents_seal(self):
        (self.root / "original-attempt/cameras/approach/000899.png").unlink()
        with self.assertRaisesRegex(ValueError, "camera frame missing"):
            publish(self.root, case_id="exact-test-case", restoration={"restored": True})
        self.assertFalse((self.root / "capture-seal.json").exists())

    def test_unrestored_native_world_prevents_publication(self):
        with self.assertRaisesRegex(ValueError, "verified Native restoration"):
            publish(self.root, case_id="exact-test-case", restoration={"restored": False})
        self.assertFalse((self.root / "trace.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
