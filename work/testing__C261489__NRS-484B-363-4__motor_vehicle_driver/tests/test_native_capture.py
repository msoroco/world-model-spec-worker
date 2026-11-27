"""CPU fake of one full original Native episode and restoration path."""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_capture
from test_school_pass import rows, scene


class FakeWorld:
    def __init__(self):
        self.settings = types.SimpleNamespace(synchronous_mode=False, fixed_delta_seconds=None)
        self.frame = 9999

    def get_settings(self):
        return self.settings

    def apply_settings(self, value):
        self.settings = value

    def tick(self):
        self.frame += 1
        return self.frame

    def get_snapshot(self):
        return types.SimpleNamespace(frame=self.frame,
                                     timestamp=types.SimpleNamespace(elapsed_seconds=1 + (self.frame - 10000) / 20))


class FakeEncoder:
    def __init__(self, path):
        path.write_bytes(b"fake camera bytes for code-path test")
        self.stdin = io.BytesIO()
        self.stderr = io.BytesIO()

    def wait(self, timeout=None):
        return 0

    def poll(self):
        return 0


class FakeAdapter:
    def __init__(self, site):
        self.site = site
        self.original = rows(site)
        self.calls = []

    def read_original_context(self, site, case_id):
        return dict(site)

    def control_frame(self, case_id, index):
        self.calls.append((case_id, index))

    def read_original_frame(self, case_id, index, frame):
        row = dict(self.original[index])
        row.update(native_frame=frame, frame=index, time_s=index / 20,
                   ego_actor_id=1, target_actor_id=2,
                   ego_vehicle_blueprint="vehicle.tesla.model3",
                   target_vehicle_blueprint="vehicle.audi.a2",
                   ego_body_vertices_m=[[0, 0, 0]] * 4,
                   target_body_vertices_m=[[1, 0, 0]] * 4)
        return row

    def camera_rgb24(self, view, frame):
        return b"\x01\x02\x03"


class FakePipelineCapture:
    calls = []

    def __init__(self, client, ego, output, case_id):
        self.case_id = case_id
        self.calls.append(("init", case_id))

    def __enter__(self):
        return self

    def capture(self, frame, elapsed):
        self.calls.append((frame, elapsed))

    def __exit__(self, kind, value, traceback):
        self.calls.append(("close", kind))


class NativeCaptureTests(unittest.TestCase):
    def test_exact_original_frames_four_cameras_and_world_restore(self):
        scratch = Path(os.environ["TMPDIR"])
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            output = Path(directory)
            site = scene()
            site["_source_sha256"] = "a" * 64
            site["map_sha256"] = "b" * 64
            adapter = FakeAdapter(site)
            world = FakeWorld()
            module = types.ModuleType("pipeline_capture")
            module.PipelineCapture = FakePipelineCapture
            FakePipelineCapture.calls = []
            def encode(root, view):
                return FakeEncoder(root / (view + ".mkv"))
            with patch.dict(sys.modules, {"pipeline_capture": module}), \
                 patch.object(native_capture, "SIZES", {view: (1, 1) for view in native_capture.VIEWS}), \
                 patch.object(native_capture, "encoder", encode):
                result = native_capture.capture(object(), world, adapter, object(), site,
                                                site["case_id"], output, site["_source_sha256"])
            self.assertEqual(len(adapter.calls), 900)
            self.assertEqual(len([x for x in FakePipelineCapture.calls if type(x[0]) is int]), 900)
            self.assertEqual(json.loads(Path(result["receipt"]).read_text())["frame_count"], 900)
            self.assertFalse(world.get_settings().synchronous_mode)
            self.assertIsNone(world.get_settings().fixed_delta_seconds)
            self.assertEqual(len(Path(result["trace"]).read_text().splitlines()), 900)

    def test_missing_second_vehicle_readback_rejected(self):
        row = {"native_frame": 4, "original_frame": 4, "frame": 0, "time_s": 0}
        with self.assertRaisesRegex(ValueError, "two-vehicle readback missing"):
            native_capture.validate_frame(row, 0, 4, 1.0)


if __name__ == "__main__":
    unittest.main()
