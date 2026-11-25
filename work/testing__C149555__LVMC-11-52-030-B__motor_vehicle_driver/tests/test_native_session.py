import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("native_session", ROOT / "native_session.py")
session = importlib.util.module_from_spec(spec)
spec.loader.exec_module(session)


class NativeSessionTests(unittest.TestCase):
    def dependencies(self, events, *, fail_capture=False):
        class World:
            def get_settings(self):
                return SimpleNamespace(synchronous_mode=False, fixed_delta_seconds=None)
            def apply_settings(self, settings):
                events.append(("settings", settings.synchronous_mode,
                               settings.fixed_delta_seconds))
        class Client:
            world = World()
            def get_world(self):
                return self.world
        class Restore:
            @staticmethod
            def snapshot(client):
                events.append("snapshot")
                return {"saved": True}
            @staticmethod
            def restore(client, saved):
                events.append("restore")
                return {"restored": True}
        class Adapter:
            def __init__(self, world, site, dossier):
                events.append("adapter")
                self.ego = None
            def sample_original(self, *_):
                return {}
            def cleanup(self):
                events.append("cleanup")
        def prepare(adapter, *_):
            events.append("prepare")
            adapter.ego = object()
        class Cameras:
            def __init__(self, adapter, site):
                events.append("camera-init")
            def __enter__(self):
                events.append("camera-enter")
                return self
            def __exit__(self, *_):
                events.append("camera-exit")
            def read_camera(self, *_):
                return None
        class Pipeline:
            def __init__(self, client, ego, output, case):
                events.append("pipeline-init")
            def __enter__(self):
                events.append("pipeline-enter")
                return self
            def __exit__(self, *_):
                events.append("pipeline-exit")
        def capture(*args, **kwargs):
            events.append("capture")
            if fail_capture:
                raise RuntimeError("original capture failed")
            return [{}] * 900
        def encode(output):
            events.append("encode")
            return {"overview": {"path": "overview.mkv"}}
        def compose(sources, frame_map, output):
            events.append("compose")
            return {"primary": str(output)}
        return Client(), dict(adapter_factory=Adapter, camera_rig_factory=Cameras,
                              pipeline_capture_class=Pipeline, frame_capture=capture,
                              encoder=encode, composer=compose,
                              world_restore_module=Restore, scene_preparer=prepare)

    def test_owned_capture_order_and_world_restoration(self):
        scratch = Path.cwd() / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            prior = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
            os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = temp
            try:
                events = []
                client, deps = self.dependencies(events)
                result = session.capture_session(client, {}, {}, case_id="case",
                    variant="freight_loading", output=Path(temp), **deps)
                self.assertEqual(result["frames"], 900)
                self.assertEqual(result["restoration"], {"restored": True})
                self.assertEqual(events[-4:], ["encode", "compose", "cleanup", "restore"])
                self.assertLess(events.index("pipeline-exit"), events.index("camera-exit"))
                self.assertLess(events.index("camera-exit"), events.index("cleanup"))
            finally:
                if prior is None:
                    os.environ.pop("SCENARIO_PIPELINE_OUTPUT_ROOT", None)
                else:
                    os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = prior

    def test_capture_failure_still_restores_world(self):
        scratch = Path.cwd() / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            prior = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
            os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = temp
            try:
                events = []
                client, deps = self.dependencies(events, fail_capture=True)
                with self.assertRaisesRegex(RuntimeError, "original capture failed"):
                    session.capture_session(client, {}, {}, case_id="case",
                        variant="freight_loading", output=Path(temp), **deps)
                self.assertEqual(events[-2:], ["cleanup", "restore"])
            finally:
                if prior is None:
                    os.environ.pop("SCENARIO_PIPELINE_OUTPUT_ROOT", None)
                else:
                    os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = prior
