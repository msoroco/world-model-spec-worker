import hashlib
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase, mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import native_runner


class World:
    def __init__(self):
        self.settings = SimpleNamespace(synchronous_mode=False,
                                        fixed_delta_seconds=None)
        self.applied = []

    def get_settings(self):
        return self.settings

    def apply_settings(self, settings):
        self.settings = settings
        self.applied.append((settings.synchronous_mode,
                             settings.fixed_delta_seconds))


class RunnerTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.map_bytes = b"original OpenDRIVE bytes"
        packet = {"source_kind": "original_map_survey",
                  "map_sha256": hashlib.sha256(self.map_bytes).hexdigest()}
        self.survey = self.root / "survey.json"
        self.survey.write_text(json.dumps(packet) + "\n")
        self.survey_hash = hashlib.sha256(self.survey.read_bytes()).hexdigest()
        self.world = World()

    def run_case(self, map_reader=None):
        return native_runner.run_capture(
            self.world, object(), survey_path=self.survey,
            survey_sha256=self.survey_hash, case_id=ROOT.name + "__open_near_clear",
            output=self.root / "output", map_reader=map_reader or
            (lambda world: self.map_bytes), actor_factory=lambda *args: None,
            driver_act_controller=lambda *args: None,
            original_observer=lambda *args: None)

    def test_clock_and_world_restored_after_capture(self):
        seal = self.root / "capture-seal.json"
        seal.write_text('{"sealed":true}\n')
        with mock.patch.object(native_runner, "capture", return_value={"frame_count": 900}) as run, \
             mock.patch.object(native_runner, "publish", return_value=seal) as publish:
            result = self.run_case()
        self.assertEqual(result["frame_count"], 900)
        self.assertEqual(result["capture_seal_sha256"], hashlib.sha256(seal.read_bytes()).hexdigest())
        self.assertTrue(publish.call_args.kwargs["restoration_verified"])
        self.assertEqual(self.world.applied, [(True, .05), (False, None)])
        self.assertEqual(run.call_args.args[0].map_sha256(),
                         hashlib.sha256(self.map_bytes).hexdigest())

    def test_world_restored_after_capture_failure(self):
        with mock.patch.object(native_runner, "capture", side_effect=ValueError("missing act")):
            with self.assertRaisesRegex(ValueError, "missing act"):
                self.run_case()
        self.assertEqual(self.world.applied[-1], (False, None))

    def test_wrong_map_rejected_before_world_mutation(self):
        with self.assertRaisesRegex(ValueError, "loaded map bytes"):
            self.run_case(map_reader=lambda world: b"foreign map")
        self.assertEqual(self.world.applied, [])

    def test_nonbyte_map_rejected_before_world_mutation(self):
        with self.assertRaisesRegex(ValueError, "map bytes"):
            self.run_case(map_reader=lambda world: "map name")
        self.assertEqual(self.world.applied, [])

    def test_clock_readback_failure_restores_world(self):
        def refused(settings):
            if settings.synchronous_mode:
                self.world.applied.append((True, settings.fixed_delta_seconds))
            else:
                self.world.settings = settings
                self.world.applied.append((False, None))
        self.world.apply_settings = refused
        with self.assertRaisesRegex(ValueError, "clock readback"):
            self.run_case()
        self.assertEqual(self.world.applied[-1], (False, None))
