import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parents[1] / "runtime"))
spec = importlib.util.spec_from_file_location("native_capture", ROOT / "native_capture.py")
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)
encode_spec = importlib.util.spec_from_file_location("encode_cameras", ROOT / "encode_cameras.py")
encoding = importlib.util.module_from_spec(encode_spec)
encode_spec.loader.exec_module(encoding)
from freight_contract import SourceError


CASE_ID = "testing__C149555__LVMC-11-52-030-B__motor_vehicle_driver__freight_loading"


class FakeWorld:
    def __init__(self):
        self.frame = 100
    def tick(self):
        self.frame += 1
        return self.frame
    def get_snapshot(self):
        timestamp = type("Timestamp", (), {"elapsed_seconds": (self.frame - 101) / 20})()
        return type("Snapshot", (), {"frame": self.frame, "timestamp": timestamp})()


class FakeAdapter:
    def __init__(self):
        self.world = FakeWorld()
        self.phase = "approach"
        self.calls = []
    def step_capture(self, index):
        self.calls.append(index)
        if index >= 200:
            self.phase = "hold"
        return {"phase": self.phase}


class NativeCaptureTests(unittest.TestCase):
    def test_each_original_sample_follows_its_single_world_tick(self):
        scratch = Path.cwd() / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as tmp:
            prior = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
            os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = tmp
            try:
                adapter = FakeAdapter()
                def sample(index, frame, snapshot):
                    self.assertEqual(adapter.calls[-1], index)
                    return {"original_frame": index, "native_frame": frame,
                            "time_s": snapshot.timestamp.elapsed_seconds,
                            "ego_station_m": 5 + min(index, 200) / 8}
                rows = capture.capture_original_frames(adapter, sample, Path(tmp), case_id=CASE_ID)
                self.assertEqual(len(rows), 900)
                self.assertEqual(adapter.world.frame, 1000)
                frame_rows = [json.loads(line) for line in
                              (Path(tmp) / "frame-map.jsonl").read_text().splitlines()]
                self.assertEqual(len(frame_rows), 900)
                self.assertEqual(frame_rows[0]["carla_frame"], 101)
                self.assertEqual(frame_rows[-1]["video_frame"], 899)
                index = json.loads((Path(tmp) / "frame-index.json").read_text())
                self.assertEqual(index["case_id"], CASE_ID)
                self.assertEqual(index["frames"], list(range(900)))
                self.assertEqual(len((Path(tmp) / "freight_motion.jsonl").read_text().splitlines()), 900)
            finally:
                if prior is None:
                    os.environ.pop("SCENARIO_PIPELINE_OUTPUT_ROOT", None)
                else:
                    os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = prior

    def test_rejects_missing_runtime_output_route(self):
        prior = os.environ.pop("SCENARIO_PIPELINE_OUTPUT_ROOT", None)
        try:
            with self.assertRaisesRegex(SourceError, "SCENARIO_PIPELINE_OUTPUT_ROOT"):
                capture.capture_original_frames(FakeAdapter(), lambda *_: {}, Path.cwd(),
                                                case_id=CASE_ID)
        finally:
            if prior is not None:
                os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = prior

    def test_four_camera_and_pipeline_frames_join_same_native_tick(self):
        scratch = Path.cwd() / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as tmp:
            prior = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
            os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = tmp
            try:
                adapter = FakeAdapter()
                class Pipeline:
                    def capture(self, frame, time_s):
                        return {"frame": frame, "time_s": time_s}
                sample = lambda index, frame, snapshot: {
                    "original_frame": index, "native_frame": frame,
                    "time_s": snapshot.timestamp.elapsed_seconds,
                    "ego_station_m": 5 + min(index, 200) / 8}
                png = b"\x89PNG\r\n\x1a\nsource-shaped-fixture"
                capture.capture_original_frames(
                    adapter, sample, Path(tmp), case_id=CASE_ID,
                    native_capture=Pipeline(), read_camera=lambda name, frame: (frame, png))
                for name in ("overview", "approach", "reference_corner", "driver_reference"):
                    rows = [json.loads(line) for line in
                            (Path(tmp) / (name + "-camera.jsonl")).read_text().splitlines()]
                    self.assertEqual(len(rows), 900)
                    self.assertEqual(rows[-1]["native_frame"], 1000)
                    self.assertTrue((Path(tmp) / rows[-1]["path"]).is_file())
                commands = []
                def fake_encoder(command, **_):
                    commands.append(command)
                    Path(command[-1]).write_bytes(command[-1].encode())
                    return type("Result", (), {"returncode": 0})()
                def fake_probe(path):
                    width, height = encoding.CAMERAS[path.stem]
                    return {"width": width, "height": height,
                            "r_frame_rate": "20/1", "nb_read_frames": "900"}
                media = encoding.encode_cameras(Path(tmp), run_encoder=fake_encoder,
                                                media_probe=fake_probe)
                self.assertEqual(set(media), set(encoding.CAMERAS))
                self.assertEqual(len(commands), 4)
                self.assertTrue(all("ffv1" in command for command in commands))
                pixel = Path(tmp) / "cameras" / "overview" / "000000.png"
                pixel.write_bytes(pixel.read_bytes() + b"tampered")
                with self.assertRaisesRegex(SourceError, "stale original camera pixels"):
                    encoding.encode_cameras(Path(tmp), run_encoder=fake_encoder,
                                            media_probe=fake_probe)
            finally:
                if prior is None:
                    os.environ.pop("SCENARIO_PIPELINE_OUTPUT_ROOT", None)
                else:
                    os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = prior
