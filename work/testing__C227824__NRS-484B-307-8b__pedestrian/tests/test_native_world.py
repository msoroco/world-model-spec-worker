import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_world import run_with_client, run_native


class World:
    def __init__(self):
        self.settings = NS(synchronous_mode=False, fixed_delta_seconds=None,
                           no_rendering_mode=True)

    def get_settings(self):
        return self.settings

    def apply_settings(self, settings):
        self.settings = settings


class Client:
    def __init__(self):
        self.world = World()
        self.loaded = None

    def generate_opendrive_world(self, source):
        self.loaded = source
        return self.world


class Actor:
    def __init__(self):
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class Recorder:
    def __init__(self, sensors, root):
        self.closed = False

    def close(self):
        self.closed = True


class NativeWorldTests(unittest.TestCase):
    def setUp(self):
        safe = Path(__file__).resolve().parents[3] / ".runtime-work"
        safe.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=safe)
        self.root = Path(self.temp.name)
        self.scene = {"case_id": "testing__C227824__NRS-484B-307-8b__pedestrian__red_no_device_entry",
                      "planned_frames": 3}
        map_bytes = b"<OpenDRIVE/>\n"
        self.scene["map_source_sha256"] = hashlib.sha256(map_bytes).hexdigest()
        (self.root / "candidate-corridor.xodr").write_bytes(map_bytes)
        (self.root / "scene.json").write_text(json.dumps(self.scene) + "\n")
        (self.root / "construction.json").write_text("{}\n")
        (self.root / "runner.py").write_text("# runner\n")
        self.client = Client()
        self.walker = Actor()
        self.cameras = {name: Actor() for name in
                        ("overview", "approach", "reference_corner", "driver_reference")}
        self.recorders = []
        self.seals = []

    def tearDown(self):
        self.temp.cleanup()

    def _recorder(self, sensors, root):
        recorder = Recorder(sensors, root)
        self.recorders.append(recorder)
        return recorder

    def _run(self, restored=True, capture_failure=False):
        def capture(*args, **kwargs):
            if capture_failure:
                raise ValueError("original frame failed")
            return {"frame_count": 3}

        def seal(*args, **kwargs):
            self.seals.append(kwargs)

        with patch("native_world.run_ticks", side_effect=capture), \
             patch("native_world.source_hashes", return_value={"scene.json": {"sha256": "a" * 64}}):
            return run_with_client(self.scene, self.root, self.client, NS(),
                                   snapshot_world=lambda client: {"prior": True},
                                   restore_world=lambda client, prior: {"restored": restored},
                                   seal_capture=seal,
                                   camera_factory=lambda world, carla, scene: self.cameras,
                                   recorder_factory=self._recorder,
                                   walker_factory=lambda world, carla, scene: self.walker)

    def test_world_restored_and_original_assets_destroyed_before_seal(self):
        result = self._run()
        self.assertTrue(result["native_capture_sealed"])
        self.assertEqual(self.client.loaded, "<OpenDRIVE/>\n")
        self.assertTrue(self.client.world.settings.synchronous_mode)
        self.assertTrue(self.walker.destroyed)
        self.assertTrue(all(actor.destroyed for actor in self.cameras.values()))
        self.assertTrue(self.recorders[0].closed)
        self.assertEqual(self.seals[0]["frames"], 3)

    def test_capture_failure_or_failed_restoration_cannot_seal(self):
        with self.assertRaisesRegex(RuntimeError, "acquisition or restoration failed"):
            self._run(capture_failure=True)
        self.assertEqual(self.seals, [])
        self.assertTrue(self.walker.destroyed)
        self.assertTrue(self.recorders[0].closed)

    def test_failed_world_restoration_cannot_seal(self):
        with self.assertRaisesRegex(RuntimeError, "acquisition or restoration failed"):
            self._run(restored=False)
        self.assertEqual(self.seals, [])
        self.assertTrue(self.walker.destroyed)

    def test_changed_materialized_map_rejected_before_world_mutation(self):
        (self.root / "candidate-corridor.xodr").write_text("changed")
        with self.assertRaisesRegex(ValueError, "OpenDRIVE map differs"):
            self._run()
        self.assertIsNone(self.client.loaded)

    def test_native_entrypoint_sets_private_runtime_before_pipeline_import(self):
        class FakeClient(Client):
            def set_timeout(self, seconds):
                self.timeout = seconds

        fake_carla = NS(Client=lambda host, port: FakeClient())
        with patch.dict(sys.modules, {"carla": fake_carla}), \
             patch("native_world.run_with_client", return_value={"prepared": True}) as run:
            result = run_native(self.scene, self.root)
        self.assertTrue(result["prepared"])
        self.assertEqual(Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).parent,
                         (Path(__file__).resolve().parents[3] / ".runtime-work").resolve())
        self.assertTrue(any("runtime/scenario_pipeline" in path for path in sys.path))
        self.assertTrue(run.called)


if __name__ == "__main__":
    unittest.main()
