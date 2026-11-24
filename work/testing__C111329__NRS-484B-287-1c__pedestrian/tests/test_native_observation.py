import copy
import hashlib
from io import BytesIO
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_observation import analyze_saved, capture_observation
from saved_camera_audit import audit_saved
from PIL import Image
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

    def _camera_capture(self, ticks=5):
        buffer = BytesIO()
        Image.new("RGB", (8, 6), (30, 60, 90)).save(buffer, format="PNG")
        payload = buffer.getvalue()
        names = ("overview", "approach", "reference_corner", "driver_reference")
        readers = {name: lambda frame, payload=payload: {"frame": frame,
                   "png_bytes": payload} for name in names}
        dims = {name: (8, 6) for name in names}
        receipt = capture_observation(self.world, self.walker, self.packet, "case-one",
                    self.path, self.read_device, ticks=ticks, camera_readers=readers,
                    camera_dimensions=dims)
        return receipt, dims

    def test_four_camera_full_decode_and_motion_join(self):
        receipt, dims = self._camera_capture()
        result = audit_saved(self.packet, receipt, expected_case_id="case-one",
                             required_frames=5, camera_dimensions=dims)
        self.assertEqual(result["decoded_images"], 20)
        self.assertTrue(result["motion"]["crossed_both_highway_banks"])
        self.assertFalse(result["physical_acceptance"])

    def test_full_duration_camera_profile_and_decode(self):
        receipt, dims = self._camera_capture(ticks=900)
        result = audit_saved(self.packet, receipt, expected_case_id="case-one",
                             required_frames=900, camera_dimensions=dims)
        self.assertEqual(result["decoded_images"], 3600)
        self.assertEqual(result["frame_count"], 900)

    def test_camera_audit_rejects_missing_camera_capture(self):
        receipt = self.capture()
        with self.assertRaisesRegex(ValueError, "four-camera capture missing"):
            audit_saved(self.packet, receipt, expected_case_id="case-one", required_frames=5)

    def test_camera_audit_rejects_archive_tamper_and_frame_binding(self):
        receipt, dims = self._camera_capture()
        document = json.loads(self.path.read_text())
        archive = Path(document["camera_sources"]["overview"]["path"])
        archive.write_bytes(archive.read_bytes() + b"tamper")
        with self.assertRaisesRegex(ValueError, "source hash mismatch"):
            audit_saved(self.packet, receipt, expected_case_id="case-one",
                        required_frames=5, camera_dimensions=dims)
        document["camera_sources"]["overview"]["sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
        document["frames"][0]["camera_frames"]["overview"]["sha256"] = "0" * 64
        self.path.write_text(json.dumps(document))
        receipt["sha256"] = hashlib.sha256(self.path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "pixel binding mismatch"):
            audit_saved(self.packet, receipt, expected_case_id="case-one",
                        required_frames=5, camera_dimensions=dims)

    def test_camera_capture_rejects_unsynchronized_reader(self):
        names = ("overview", "approach", "reference_corner", "driver_reference")
        readers = {name: lambda frame: {"frame": frame + 1, "png_bytes": b""}
                   for name in names}
        with self.assertRaisesRegex(ValueError, "camera frame identity mismatch"):
            capture_observation(self.world, self.walker, self.packet, "case-one",
                self.path, self.read_device, ticks=5, camera_readers=readers,
                camera_dimensions={name: (8, 6) for name in names})
        self.assertFalse(self.path.exists())
        self.assertFalse(list(Path(self.tmp.name).glob("*.zip")))


if __name__ == "__main__":
    unittest.main()
