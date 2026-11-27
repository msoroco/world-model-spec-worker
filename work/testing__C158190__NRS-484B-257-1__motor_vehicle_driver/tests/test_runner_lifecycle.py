"""Native sealing follows actor teardown and stops on capture failure."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runner


class Adapter:
    def __init__(self, events):
        self.events = events

    def destroy(self, actor):
        self.events.append("destroy:" + actor)

    def map_bytes(self, world):
        self.events.append("map_readback")
        return b"original map"


class RunnerLifecycleTests(unittest.TestCase):
    def run_with_capture(self, capture):
        events = []
        adapter = Adapter(events)

        def construct(*args):
            events.append("construct")
            return {"yield_sign_actor_id": "sign", "through_vehicle_actor_id": "through"}

        def publish(*args, **kwargs):
            events.append("publish")
            self.assertTrue(kwargs["restored"])
            self.assertEqual(kwargs["map_bytes"], b"original map")
            return {"sealed": True}

        with patch.object(runner, "construct", side_effect=construct), \
                patch.object(runner, "capture", side_effect=capture), \
                patch.object(runner, "publish", side_effect=publish):
            result = runner.run_attempt(object(), adapter, {}, "site", "case", "attempt", "hash")
        return events, result

    def test_capture_cleanup_precedes_publish(self):
        events = []

        def capture(*args):
            events.append("capture")

        # Capture uses its own event list here; the ordering that matters is
        # teardown and map readback before the publish call.
        observed, result = self.run_with_capture(capture)
        self.assertEqual(observed, ["construct", "destroy:through", "destroy:sign",
                                    "map_readback", "publish"])
        self.assertEqual(events, ["capture"])
        self.assertEqual(result, {"sealed": True})

    def test_failed_capture_releases_actors_without_publish(self):
        events = []
        adapter = Adapter(events)

        with patch.object(runner, "construct", return_value={
                "yield_sign_actor_id": "sign", "through_vehicle_actor_id": "through"}), \
                patch.object(runner, "capture", side_effect=ValueError("camera failed")), \
                patch.object(runner, "publish") as publish:
            with self.assertRaisesRegex(ValueError, "camera failed"):
                runner.run_attempt(object(), adapter, {}, "site", "case", "attempt", "hash")
        self.assertEqual(events, ["destroy:through", "destroy:sign"])
        publish.assert_not_called()

    def test_failed_through_release_still_releases_sign(self):
        events = []

        class FailingAdapter(Adapter):
            def destroy(self, actor):
                super().destroy(actor)
                if actor == "through":
                    raise ValueError("through release failed")

        adapter = FailingAdapter(events)
        with patch.object(runner, "construct", return_value={
                "yield_sign_actor_id": "sign", "through_vehicle_actor_id": "through"}), \
                patch.object(runner, "capture"), \
                patch.object(runner, "publish") as publish:
            with self.assertRaisesRegex(ValueError, "through release failed"):
                runner.run_attempt(object(), adapter, {}, "site", "case", "attempt", "hash")
        self.assertEqual(events, ["destroy:through", "destroy:sign"])
        publish.assert_not_called()


if __name__ == "__main__":
    unittest.main()
