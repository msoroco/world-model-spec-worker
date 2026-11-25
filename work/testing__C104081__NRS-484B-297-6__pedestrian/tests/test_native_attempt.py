import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_attempt import run_native_attempt


class World:
    def __init__(self):
        self.synchronous_mode = False
        self.fixed_delta_seconds = None
        self.refuse_settings = False

    def get_settings(self):
        return self

    def apply_settings(self, settings):
        if self.refuse_settings:
            self.synchronous_mode = False
            self.fixed_delta_seconds = None


class Client:
    def __init__(self):
        self.world = World()

    def get_world(self):
        return self.world


class Restore:
    def __init__(self):
        self.calls = []
        self.fail = False

    def snapshot(self, client):
        self.calls.append("snapshot")
        return {"original": True}

    def restore(self, client, saved):
        self.calls.append("restore")
        if self.fail:
            raise RuntimeError("restore readback differs")
        return {"restored": True, "map": "original"}


class Adapter:
    def __init__(self):
        self.destroyed = []

    def destroy(self, handle):
        self.destroyed.append(handle)


class Recorder:
    def __init__(self):
        self.aborted = False

    def abort(self):
        self.aborted = True


class NativeAttemptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "attempt"
        self.survey = Path(self.temp.name) / "survey.json"
        self.survey.write_text("{}\n")
        self.restore = Restore()
        self.adapter = Adapter()
        self.recorder = Recorder()
        self.case = "testing__C104081__NRS-484B-297-6__pedestrian__blocked_intervening"
        self.kwargs = dict(restore_api=self.restore, camera_profile_sha256="a" * 64,
                           traffic_plan_sha256="b" * 64,
                           pedestrian_blueprint="walker.pedestrian.0001")

    def run_attempt(self):
        return run_native_attempt(
            Client(), object(), {}, self.case, self.survey, "c" * 64,
            self.adapter, lambda *args: lambda sample: {}, self.recorder, self.output,
            **self.kwargs,
        )

    def test_success_seals_audit_and_restores_after_reverse_destruction(self):
        constructed = {"owned_handles": ["obstacle", "walker"]}
        client = Client()
        def capture(*args, **kwargs):
            packet_output = args[7]
            packet_output.mkdir()
            (packet_output / "source-packet.json").write_text('{"sealed": true}\n')
        packet_sha256 = hashlib.sha256(b'{"sealed": true}\n').hexdigest()
        with patch("native_attempt.construct_native", return_value=constructed), \
             patch("native_attempt.capture_constructed_sources", side_effect=capture), \
             patch("native_attempt.audit_saved", return_value={"checks": {"full_video_decode": True},
                                                               "source_packet_sha256": packet_sha256}):
            result = run_native_attempt(
                client, object(), {}, self.case, self.survey, "c" * 64,
                self.adapter, lambda *args: lambda sample: {}, self.recorder,
                self.output, **self.kwargs)
        self.assertTrue(client.world.synchronous_mode)
        self.assertEqual(client.world.fixed_delta_seconds, 0.05)
        self.assertEqual(self.adapter.destroyed, ["walker", "obstacle"])
        self.assertEqual(self.restore.calls, ["snapshot", "restore"])
        self.assertEqual(result["source_packet_sha256"], hashlib.sha256(
            (self.output / "source-packet.json").read_bytes()).hexdigest())
        self.assertEqual(json.loads((self.output / "lifecycle-receipt.json").read_text()), result)
        self.assertEqual(result["physical_acceptance"], "not_assessed")

    def test_capture_failure_still_destroys_and_restores(self):
        with patch("native_attempt.construct_native", return_value={"owned_handles": ["obstacle", "walker"]}), \
             patch("native_attempt.capture_constructed_sources", side_effect=ValueError("stale frame")):
            with self.assertRaisesRegex(ValueError, "stale frame"):
                self.run_attempt()
        self.assertEqual(self.adapter.destroyed, ["walker", "obstacle"])
        self.assertEqual(self.restore.calls, ["snapshot", "restore"])
        self.assertTrue(self.recorder.aborted)
        self.assertFalse((self.output / "lifecycle-receipt.json").exists())

    def test_changed_saved_audit_source_prevents_receipt(self):
        def capture(*args, **kwargs):
            packet_output = args[7]
            packet_output.mkdir()
            (packet_output / "source-packet.json").write_text('{"sealed": true}\n')
        with patch("native_attempt.construct_native", return_value={"owned_handles": ["walker"]}), \
             patch("native_attempt.capture_constructed_sources", side_effect=capture), \
             patch("native_attempt.audit_saved", return_value={"checks": {"full_video_decode": True},
                                                               "source_packet_sha256": "0" * 64}):
            with self.assertRaisesRegex(ValueError, "source packet seal differ"):
                self.run_attempt()
        self.assertEqual(self.adapter.destroyed, ["walker"])
        self.assertTrue(self.recorder.aborted)
        self.assertEqual(self.restore.calls, ["snapshot", "restore"])
        self.assertFalse((self.output / "lifecycle-receipt.json").exists())

    def test_core_and_packet_stage_keep_identical_original_survey(self):
        import types
        self.output.mkdir()
        (self.output / "site-survey.json").write_bytes(self.survey.read_bytes())
        calls = []
        def core_factory(client, walker, output, case):
            return types.SimpleNamespace(
                capture=lambda frame, time: calls.append((frame, time)),
                close=lambda confirmed=True: calls.append(("close", confirmed)))
        def capture(*args, **kwargs):
            packet_output = args[7]
            packet_output.mkdir()
            (packet_output / "site-survey.json").write_bytes(self.survey.read_bytes())
            (packet_output / "source-packet.json").write_text('{"sealed": true}\n')
            kwargs["on_core_sample"](10, .5)
        packet_sha256 = hashlib.sha256(b'{"sealed": true}\n').hexdigest()
        with patch("native_attempt.construct_native", return_value={"owned_handles": ["walker"]}), \
             patch("native_attempt.capture_constructed_sources", side_effect=capture), \
             patch("native_attempt.audit_saved", return_value={"checks": {"full_video_decode": True},
                                                              "source_packet_sha256": packet_sha256}):
            run_native_attempt(Client(), object(), {}, self.case, self.survey,
                               "c" * 64, self.adapter, lambda *args: lambda sample: {},
                               self.recorder, self.output,
                               core_capture_factory=core_factory, **self.kwargs)
        self.assertEqual(calls, [(10, .5), ("close", True), ("close", True)])
        self.assertEqual((self.output / "site-survey.json").read_bytes(), self.survey.read_bytes())

    def test_restore_failure_prevents_success_receipt(self):
        self.restore.fail = True
        with patch("native_attempt.construct_native", return_value={"owned_handles": ["walker"]}), \
             patch("native_attempt.capture_constructed_sources", side_effect=ValueError("stale frame")):
            with self.assertRaisesRegex(RuntimeError, "world restore"):
                self.run_attempt()
        self.assertEqual(self.adapter.destroyed, ["walker"])
        self.assertFalse((self.output / "lifecycle-receipt.json").exists())

    def test_missing_recorder_rejected_before_snapshot(self):
        with self.assertRaisesRegex(ValueError, "four-camera"):
            run_native_attempt(Client(), object(), {}, self.case, self.survey,
                               "c" * 64, self.adapter, lambda *args: None,
                               None, self.output, **self.kwargs)
        self.assertEqual(self.restore.calls, [])

    def test_clock_readback_failure_prevents_capture_and_restores(self):
        client = Client()
        client.world.refuse_settings = True
        with patch("native_attempt.construct_native") as construct:
            with self.assertRaisesRegex(ValueError, "20 Hz synchronous clock"):
                run_native_attempt(client, object(), {}, self.case, self.survey,
                                   "c" * 64, self.adapter,
                                   lambda *args: lambda sample: {}, self.recorder,
                                   self.output, **self.kwargs)
        construct.assert_not_called()
        self.assertEqual(self.restore.calls, ["snapshot", "restore"])
        self.assertFalse((self.output / "lifecycle-receipt.json").exists())

    def test_owned_camera_factory_runs_after_snapshot_and_closes_before_restore(self):
        client = Client()
        calls = self.restore.calls
        rig = type("Rig", (), {})()
        rig.recorder = Recorder()
        rig.close = lambda: calls.append("close rig")
        def factory(world):
            self.assertIs(world, client.world)
            calls.append("create rig")
            return rig
        with patch("native_attempt.construct_native", return_value={"owned_handles": ["walker"]}), \
             patch("native_attempt.capture_constructed_sources", side_effect=ValueError("stale frame")):
            with self.assertRaisesRegex(ValueError, "stale frame"):
                run_native_attempt(client, object(), {}, self.case, self.survey,
                    "c" * 64, self.adapter, lambda *args: lambda sample: {},
                    None, self.output, camera_rig_factory=factory, **self.kwargs)
        self.assertEqual(calls, ["snapshot", "create rig", "close rig", "restore"])
        self.assertTrue(rig.recorder.aborted)


if __name__ == "__main__":
    unittest.main()
