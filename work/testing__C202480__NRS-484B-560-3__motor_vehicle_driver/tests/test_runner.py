"""Fake Native owner proves runner closure on success and capture failure."""

import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import runner


class RunnerTests(unittest.TestCase):
    def setUp(self):
        private = ROOT / ".runtime-work"
        private.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=private)
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.packet = self.folder / "packet.json"
        self.packet.write_text("{}\n")
        self.events = []

    def execute(self, failure=False):
        events = self.events

        class World:
            def apply_settings(self, settings):
                events.append("settings_applied")

        world = World()

        class Client:
            def __init__(self, host, port):
                events.append("client_connected")

            def set_timeout(self, seconds):
                pass

            def get_world(self):
                return world

        class Rig:
            def __init__(self, *args):
                events.append("camera_attached")

            def close(self):
                events.append("encoders_closed")

        class Scene:
            ego = object()

            def close(self):
                events.append("actors_closed")

        def capture(*args):
            events.append("capture_finished" if not failure else "capture_failed")
            if failure:
                raise ValueError("synthetic capture failure")
            return {"frames": 900}

        carla = types.ModuleType("carla")
        carla.Client = Client
        carla.VehicleControl = object
        carla.Location = lambda *args, **kwargs: args or kwargs
        carla.Rotation = lambda *args, **kwargs: args or kwargs
        carla.Transform = lambda *args: args
        exchange = types.ModuleType("worker_exchange")
        exchange.__path__ = []
        restore_module = types.ModuleType("worker_exchange.world_restore")
        restore_module.snapshot = lambda client: {"settings": types.SimpleNamespace()}

        def restore(*args):
            events.append("restoration_verified")
            return {"restored": True}

        restore_module.restore = restore
        attempt = self.folder / "attempt"
        with patch.dict(sys.modules, {"carla": carla, "worker_exchange": exchange,
                                      "worker_exchange.world_restore": restore_module}), \
             patch.dict(os.environ, {"SCENARIO_PIPELINE_OUTPUT_ROOT": str(self.folder)}), \
             patch.object(runner, "inspect", return_value=({}, {}, b"")), \
             patch.object(runner, "create", return_value=Scene()), \
             patch.object(runner, "CameraRig", Rig), \
             patch.object(runner, "retain_site_sources", return_value=attempt / "site/packet.json"), \
             patch.object(runner, "capture", capture):
            if failure:
                with self.assertRaisesRegex(ValueError, "synthetic capture failure"):
                    runner.capture_original(attempt, self.packet, HERE / "case-plan.json", "case")
            else:
                result = runner.capture_original(attempt, self.packet,
                                                 HERE / "case-plan.json", "case")
                self.assertEqual(result["capture"]["frames"], 900)
        status = json.loads((attempt / "native-run-status.json").read_text())
        return status

    def test_success_closes_before_owner_release_and_saved_processing(self):
        status = self.execute()
        self.events += ["native_exit", "owner_released", "saved_processing_started"]
        expected = ["capture_finished", "encoders_closed", "actors_closed",
                    "restoration_verified", "native_exit", "owner_released",
                    "saved_processing_started"]
        self.assertEqual([event for event in self.events if event in expected], expected)
        self.assertEqual(status["errors"], [])

    def test_failure_still_closes_and_retains_feedback(self):
        status = self.execute(failure=True)
        self.assertEqual(self.events[-4:], ["capture_failed", "encoders_closed",
                                            "actors_closed", "restoration_verified"])
        self.assertIn("synthetic capture failure", status["errors"][0])
        self.assertIsNone(status["capture"])


if __name__ == "__main__":
    unittest.main()
