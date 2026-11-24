import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_observation import analyze_saved, capture_observation
import test_site_geometry


class ObservationTests(unittest.TestCase):
    def setUp(self):
        source_fixture = test_site_geometry.CrossingSiteTests("test_unmarked_and_marked_comparison")
        source_fixture.setUp()
        self.addCleanup(source_fixture.tmp.cleanup)
        self.packet = source_fixture.packet
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        class Snapshot:
            def __init__(self, frame):
                self.frame = frame
                self.timestamp = type("Timestamp", (), {"elapsed_seconds": frame * 0.05})()

        class World:
            frame = 0
            def tick(self):
                self.frame += 1
                return self.frame
            def get_snapshot(self):
                return Snapshot(self.frame)

        class Walker:
            def __init__(self, world):
                self.world = world
            def get_location(self):
                y = [-10, -5, 0, 5, 10][min(self.world.frame - 1, 4)]
                return type("Location", (), {"x": 50, "y": y, "z": 0})()

        self.world = World()
        self.walker = Walker(self.world)
        self.path = Path(self.tmp.name) / "original.json"

    @staticmethod
    def read_device(device_id):
        return {"device_id": device_id, "actor_id": 1 if device_id.startswith("east") else 2,
                "state": "Green", "is_operating": True}

    def capture(self, read_device=None):
        return capture_observation(self.world, self.walker, self.packet, "case-one",
                                   self.path, read_device or self.read_device, ticks=5)

    def test_original_capture_and_saved_crossing(self):
        receipt = self.capture()
        result = analyze_saved(self.packet, receipt, expected_case_id="case-one", required_frames=5)
        self.assertTrue(result["crossed_both_highway_banks"])
        self.assertTrue(result["both_devices_operating_all_frames"])
        self.assertTrue(result["both_devices_operating_during_crossing"])
        self.assertEqual(result["observed_crossing_frame_range"], [2, 4])
        self.assertEqual(result["legal_official_status"], "undetermined")

    def test_inactive_readback_preserved(self):
        def inactive(device_id):
            reading = self.read_device(device_id)
            if device_id.startswith("east"):
                reading["is_operating"] = False
            return reading
        receipt = self.capture(inactive)
        result = analyze_saved(self.packet, receipt, expected_case_id="case-one", required_frames=5)
        self.assertFalse(result["both_devices_operating_all_frames"])
        self.assertFalse(result["both_devices_operating_during_crossing"])

    def test_rejects_missing_original_device_identity(self):
        def missing(device_id):
            reading = self.read_device(device_id)
            reading["actor_id"] = None
            return reading
        with self.assertRaisesRegex(ValueError, "device actor identity"):
            self.capture(missing)
        self.assertFalse(self.path.exists())

    def test_rejects_stale_observation_hash(self):
        receipt = self.capture()
        self.path.write_text(self.path.read_text() + " ")
        with self.assertRaisesRegex(ValueError, "observation hash"):
            analyze_saved(self.packet, receipt, expected_case_id="case-one", required_frames=5)

    def test_rejects_wrong_case_or_incomplete_duration(self):
        receipt = self.capture()
        with self.assertRaisesRegex(ValueError, "case mismatch"):
            analyze_saved(self.packet, receipt, expected_case_id="case-two", required_frames=5)
        with self.assertRaisesRegex(ValueError, "frame count"):
            analyze_saved(self.packet, receipt, expected_case_id="case-one", required_frames=900)

    def test_rejects_source_drift(self):
        receipt = self.capture()
        packet = copy.deepcopy(self.packet)
        packet["walker_speed_mps"] = 2.0
        with self.assertRaisesRegex(ValueError, "site source binding"):
            analyze_saved(packet, receipt, expected_case_id="case-one", required_frames=5)

    def test_rejects_missing_original_crossing(self):
        self.walker.get_location = lambda: type("Location", (), {"x": 50, "y": -10, "z": 0})()
        receipt = self.capture()
        with self.assertRaisesRegex(ValueError, "did not cross"):
            analyze_saved(self.packet, receipt, expected_case_id="case-one", required_frames=5)

    def test_rejects_frame_gap(self):
        original = self.world.tick
        self.world.tick = lambda: original() * 2
        with self.assertRaisesRegex(ValueError, "frame discontinuity"):
            self.capture()

    def test_rejects_missing_saved_device_readback(self):
        receipt = self.capture()
        document = json.loads(self.path.read_text())
        del document["frames"][0]["devices"][0]["is_operating"]
        self.path.write_text(json.dumps(document))
        import hashlib
        receipt["sha256"] = hashlib.sha256(self.path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "saved device readback"):
            analyze_saved(self.packet, receipt, expected_case_id="case-one", required_frames=5)


if __name__ == "__main__":
    unittest.main()
