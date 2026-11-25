import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from finalize_lane_change import finalize
from native_construction import ASSIGNMENT
from native_readbacks import NativeReadbacks
from test_native_construction import reviewed_packet


class FakeActor:
    def __init__(self):
        self.index = 0
        self.signal = 0

    def get_transform(self):
        return SimpleNamespace(location=SimpleNamespace(
            x=self.index * 0.5, y=0.0 if self.index < 220 else min(3.5, (self.index - 219) * 0.1)))

    def get_light_state(self):
        return self.signal


class NativeReadbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd() / ".runtime-work")
        self.addCleanup(self.temp.cleanup)
        self.case = ASSIGNMENT + "__both_observed"
        self.actor = FakeActor()
        self.carla = SimpleNamespace(VehicleLightState=SimpleNamespace(LeftBlinker=4, RightBlinker=8))

    def reader(self, frame, time_s):
        return {"source_kind": "original_driver_input", "source_id": "driver-event-channel-1",
                "frame": frame, "t_s": time_s, "observed": frame == 1190}

    def test_retains_900_independent_samples_for_saved_finalizer(self):
        capture = NativeReadbacks(reviewed_packet(), self.case, self.actor,
                                  self.carla, self.reader)
        for index in range(900):
            self.actor.index = index
            self.actor.signal = 4 if index >= 180 else 0
            capture.sample(1000 + index, index * 0.05)
        root = Path(self.temp.name)
        inventory = capture.write(root, "original-native-attempt-1")
        report = finalize(root, inventory, self.case)
        self.assertTrue(report["signal_precedes_center_departure"])
        self.assertTrue(report["driver_check_observed_before_departure"])
        self.assertEqual(report["driver_check_readback_source"], "driver-event-channel-1")
        self.assertEqual(report["original_frame_count"], 900)
        self.assertEqual(report["legal_ascertainment_and_safety"], "unresolved")
        # The source hash, not merely its label, binds the saved result.
        path = root / inventory["sources"]["driver_check"]["path"]
        data = json.loads(path.read_text())
        data["samples"][190]["driver_check_observed"] = False
        path.write_text(json.dumps(data) + "\n")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            finalize(root, inventory, self.case)

    def test_controller_request_cannot_replace_independent_readback(self):
        def wrong_reader(frame, time_s):
            return {"source_kind": "controller_request", "source_id": "authored-check",
                    "frame": frame, "t_s": time_s, "observed": True}
        capture = NativeReadbacks(reviewed_packet(), self.case, self.actor,
                                  self.carla, wrong_reader)
        with self.assertRaisesRegex(ValueError, "independent original"):
            capture.sample(1000, 0.0)

    def test_changed_driver_source_and_frame_are_rejected(self):
        capture = NativeReadbacks(reviewed_packet(), self.case, self.actor,
                                  self.carla, self.reader)
        capture.sample(1000, 0.0)
        capture.check_reader = lambda frame, time_s: {
            "source_kind": "original_driver_input", "source_id": "other",
            "frame": frame, "t_s": time_s, "observed": False}
        with self.assertRaisesRegex(ValueError, "source changed"):
            capture.sample(1001, 0.05)
        capture.check_reader = lambda frame, time_s: {
            "source_kind": "original_driver_input", "source_id": "driver-event-channel-1",
            "frame": frame - 1, "t_s": time_s, "observed": False}
        with self.assertRaisesRegex(ValueError, "frame/time"):
            capture.sample(1001, 0.05)


if __name__ == "__main__":
    unittest.main()
