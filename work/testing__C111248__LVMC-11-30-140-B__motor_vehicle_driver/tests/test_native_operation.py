import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import native_operation as operation


class World:
    def __init__(self, map_name="Town"):
        self.map_name = map_name
        self.settings = SimpleNamespace(synchronous_mode=False, fixed_delta_seconds=0.1)

    def get_map(self):
        return SimpleNamespace(name=self.map_name)

    def get_settings(self):
        return self.settings

    def apply_settings(self, settings):
        self.settings = settings


class OperationTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.world = World()
        self.client = SimpleNamespace(get_world=lambda: self.world)
        self.plan = {"map_id": "Town", "case_id": "white_full_stop_wait",
                     "reviewed_source_bindings": {"packet": "a" * 64}}
        self.restore = SimpleNamespace(
            snapshot=lambda client: self.events.append("snapshot") or {"original": True},
            restore=lambda client, saved: self.events.append("restore") or {"restored": True})
        self.constructor = SimpleNamespace(destroy_actor=lambda actor: self.events.append("destroy:" + actor))
        self.recorder = SimpleNamespace(emergency_stop=lambda: self.events.append("stop"),
                                        close=lambda: self.events.append("close"))
        self.constructed = {"owned_handles": ("driver", "person", "cue")}

    def run_attempt(self, output):
        with patch.object(operation, "prepare", return_value=self.plan), \
             patch.object(operation, "construct_native", return_value=self.constructed), \
             patch.object(operation, "capture_reviewed", return_value={
                 "reviewed_source_bindings": self.plan["reviewed_source_bindings"],
                 "original_frame_count": 900}):
            return operation.run_native_attempt(
                self.client, Path("reviewed.json"), output,
                construction_adapter_factory=lambda world, plan: self.constructor,
                capture_adapter_factory=lambda world, plan, constructed: self.recorder,
                restore_api=self.restore)

    def test_success_restores_and_destroys_reverse_order(self):
        import tempfile
        with tempfile.TemporaryDirectory(dir=Path(".runtime-work").resolve()) as tmp:
            receipt = self.run_attempt(Path(tmp) / "attempt")
            self.assertEqual(receipt["original_frame_count"], 900)
            self.assertEqual(self.events,
                             ["snapshot", "stop", "close", "destroy:cue", "destroy:person", "destroy:driver", "restore"])
            self.assertTrue((Path(tmp) / "attempt" / "lifecycle-receipt.json").is_file())
            self.assertTrue(self.world.settings.synchronous_mode)
            self.assertEqual(self.world.settings.fixed_delta_seconds, 0.05)

    def test_map_mismatch_restores_without_spawn(self):
        self.world.map_name = "Other"
        with patch.object(operation, "prepare", return_value=self.plan):
            with self.assertRaisesRegex(ValueError, "map differs"):
                operation.run_native_attempt(
                    self.client, Path("reviewed.json"), Path(".runtime-work/c111248-map-mismatch"),
                    construction_adapter_factory=lambda world, plan: self.fail("spawned"),
                    capture_adapter_factory=lambda world, plan, built: self.fail("captured"),
                    restore_api=self.restore)
        self.assertEqual(self.events, ["snapshot", "restore"])

    def test_capture_failure_destroys_and_restores(self):
        with patch.object(operation, "prepare", return_value=self.plan), \
             patch.object(operation, "construct_native", return_value=self.constructed), \
             patch.object(operation, "capture_reviewed", side_effect=ValueError("capture failed")):
            with self.assertRaisesRegex(ValueError, "capture failed"):
                operation.run_native_attempt(
                    self.client, Path("reviewed.json"), Path(".runtime-work/c111248-capture-failure"),
                    construction_adapter_factory=lambda world, plan: self.constructor,
                    capture_adapter_factory=lambda world, plan, built: self.recorder,
                    restore_api=self.restore)
        self.assertEqual(self.events,
                         ["snapshot", "stop", "close", "destroy:cue", "destroy:person", "destroy:driver", "restore"])

    def test_restore_failure_is_not_a_success_receipt(self):
        import tempfile
        self.restore.restore = lambda client, saved: self.events.append("restore-failed") or {"restored": False}
        with tempfile.TemporaryDirectory(dir=Path(".runtime-work").resolve()) as tmp:
            with self.assertRaisesRegex(RuntimeError, "positive readback"):
                self.run_attempt(Path(tmp) / "attempt")
            self.assertFalse((Path(tmp) / "attempt" / "lifecycle-receipt.json").exists())

    def test_clock_readback_failure_rejected(self):
        class BadWorld(World):
            def apply_settings(self, settings):
                self.settings = SimpleNamespace(synchronous_mode=False, fixed_delta_seconds=0.1)
        with self.assertRaisesRegex(ValueError, "clock readback"):
            operation.configure_clock(BadWorld())

    def test_saved_processing_only_after_owner_release(self):
        receipt={"lifecycle_events":["capture_finished", "encoders_closed",
                                      "restoration_verified", "native_exit"],
                 "world_restore":{"restored":True}}
        events=[]
        def release(_):
            events.append("owner_released")
            return True
        def saved(_):
            self.assertEqual(events,["owner_released"])
            events.append("saved_processing_started")
        result=operation.handoff_after_release(receipt,release,saved)
        self.assertEqual(result[-2:],events)
        with self.assertRaisesRegex(ValueError,"release did not succeed"):
            operation.handoff_after_release(receipt,lambda _:False,saved)
        with self.assertRaisesRegex(ValueError,"restoration required"):
            operation.handoff_after_release(dict(receipt,world_restore={"restored":False}),release,saved)


if __name__ == "__main__":
    unittest.main()
