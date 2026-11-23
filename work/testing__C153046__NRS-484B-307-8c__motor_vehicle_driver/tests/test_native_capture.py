"""Check Native capture orchestration and attempt retention without CARLA."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_capture import capture


class NativeCaptureTests(unittest.TestCase):
    def test_actor_camera_trace_media_order_and_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            events = []
            class Actors:
                ego = object()
                signal = object()
                pedestrians = []
                traffic = []
                def close(self):
                    events.append("actors.close")
            class Rig:
                def __init__(self, *args):
                    events.append("camera.create")
                def close(self):
                    events.append("camera.close")
            class Routes:
                def __init__(self, *args):
                    events.append("routes.create")
                def before_tick(self, index):
                    pass
            def runner(*args, **kwargs):
                events.append("trace")
                self.assertEqual(kwargs["count"], 600)
                return {"samples": 600}
            def media(*args):
                events.append("media")
                return {"frames": 600}
            with patch("native_capture.create", side_effect=lambda *args: (events.append("actors.create"), Actors())[1]), \
                 patch("native_capture.Routes", Routes), \
                 patch("native_capture.CameraRig", Rig), \
                 patch("native_capture.run_carla_with_plan", side_effect=runner), \
                 patch("native_capture.finalize", side_effect=media):
                result = capture(object(), root / "site.json", "stopped_leftmost_clear",
                                 root / "attempt", object(), object(), object(), object())
            self.assertEqual(events, ["actors.create", "routes.create", "camera.create", "trace",
                                      "camera.close", "actors.close", "media"])
            self.assertFalse(result["physical_acceptance_claimed"])

    def test_wrong_duration_and_existing_attempt_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ValueError, "600 Native ticks"):
                capture(object(), root / "site.json", "stopped_leftmost_clear",
                        root / "attempt", object(), object(), object(), object(), count=1)
            attempt = root / "attempt"
            attempt.mkdir()
            (attempt / "trace.jsonl").write_text("retained")
            with self.assertRaisesRegex(ValueError, "retain previous"):
                capture(object(), root / "site.json", "stopped_leftmost_clear",
                        attempt, object(), object(), object(), object())


if __name__ == "__main__":
    unittest.main()
