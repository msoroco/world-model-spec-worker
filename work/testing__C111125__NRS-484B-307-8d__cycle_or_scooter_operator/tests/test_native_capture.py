import hashlib
import importlib.util
import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from PIL import Image


BASE = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, BASE / (name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


capture = module("native_capture")
media = module("saved_media_audit")
saved = module("saved_attempt")


class OriginalCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.authority = self.root / "authority"
        self.authority.mkdir()
        self.site = {"cell_id": "C111125", "maneuver": "straight",
                     "device_kind": "official_traffic_control_device",
                     "ego_blueprint_class": "bicycle", "ego_blueprint_id": "vehicle.bicycle.test",
                     "detector_controls_subject_signal": True, "approach_lane_id": 1,
                     "cross_lane_id": 2, "stop_boundary_station_m": 1.0,
                     "entry_station_m": 9.0}
        for name in ("map", "device", "detector", "blueprint"):
            path = self.authority / (name + ".json")
            path.write_text(json.dumps({"source": name}) + "\n")
            self.site[name + "_ref"] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        self.policy = {"device_sha256": self.site["device_ref"]["sha256"],
                       "detector_sha256": self.site["detector_ref"]["sha256"]}
        stream = BytesIO()
        Image.new("RGB", (4, 3), color=(10, 20, 30)).save(stream, format="PNG")
        self.png = stream.getvalue()
        self.full_profile = False
        self.profile_png = {}
        for name, size in capture.PROFILE_SIZES.items():
            stream = BytesIO()
            Image.new("RGB", size, color=(10, 20, 30)).save(stream, format="PNG")
            self.profile_png[name] = stream.getvalue()
        self.case_id = capture.ASSIGNMENT_ID + "__two_cycles_failed_detection"

    def tick(self, index):
        phases = ("red", "green", "yellow", "red", "green", "yellow", "red", "red", "red")
        last = self.count - 1
        station = 0.0 if index < last - 1 else (5.0 if index == last - 1 else 10.0)
        row = {"frame": index + 100, "timestamp_s": 5 + index / 20,
               "subject_signal": "red", "cross_signal": phases[index] if index < len(phases) else "red",
               "detector_occupied": True, "detector_output": False,
               "ego_speed_mps": 0.0 if station == 0 else 1.0,
               "ego_station_m": station, "directed_participant_conflict": False}
        return row, {name: self.profile_png[name] if self.full_profile else self.png for name in capture.CAMERAS}

    def make(self, count=9):
        self.count = count
        attempt = self.root / "attempt"
        capture.capture_saved(attempt_root=attempt, authority_root=self.authority,
                              site=self.site, case_suffix="two_cycles_failed_detection",
                              actor_id=23, observed_blueprint_id="vehicle.bicycle.test",
                              policy_receipt=self.policy, sample_tick=self.tick,
                              native_exit_code=0,
                              frame_count=count, diagnostic_fixture=True)
        return attempt

    def test_capture_saved_and_decode_every_original_camera(self):
        attempt = self.make()
        audit = media.audit_saved_media(attempt, self.case_id)
        self.assertEqual(audit["decoded_original_images"], 36)
        self.assertEqual(audit["camera_dimensions"], {name: [4, 3] for name in capture.CAMERAS})
        result = saved.process_saved(attempt, self.authority, self.site, self.case_id, allow_diagnostic=True)
        self.assertEqual(result["measurement"]["complete_device_cycles_before_entry"], 2)
        with self.assertRaisesRegex(saved.SavedAttemptError, "diagnostic fixture"):
            saved.process_saved(attempt, self.authority, self.site, self.case_id)

    def test_full_duration_900_frame_source_join(self):
        attempt = self.make(900)
        audit = media.audit_saved_media(attempt, self.case_id)
        self.assertEqual(audit["frame_count"], 900)
        self.assertEqual(audit["decoded_original_images"], 3600)

    def test_saved_processor_requires_camera_audit_for_original_attempt(self):
        self.full_profile = True
        attempt = self.make()
        receipt_path = attempt / "attempt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["diagnostic_fixture"] = False
        receipt_path.write_text(json.dumps(receipt) + "\n")
        result = saved.process_saved(attempt, self.authority, self.site, self.case_id)
        self.assertEqual(result["original_media_audit"]["decoded_original_images"], 36)
        (attempt / "camera-driver_reference.zip").unlink()
        with self.assertRaisesRegex(saved.SavedAttemptError, "four-camera media rejected"):
            saved.process_saved(attempt, self.authority, self.site, self.case_id)

    def test_non_diagnostic_capture_rejects_wrong_profile(self):
        self.count = 9
        with self.assertRaisesRegex(ValueError, "capture profile"):
            capture.capture_saved(attempt_root=self.root / "wrong-profile", authority_root=self.authority,
                                  site=self.site, case_suffix="two_cycles_failed_detection",
                                  actor_id=23, observed_blueprint_id="vehicle.bicycle.test",
                                  policy_receipt=self.policy, sample_tick=self.tick,
                                  native_exit_code=0,
                                  frame_count=9, diagnostic_fixture=False)

    def test_reject_camera_hash_pixel_and_missing_source(self):
        attempt = self.make()
        path = attempt / "camera-overview.zip"
        path.write_bytes(path.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "source hash mismatch"):
            media.audit_saved_media(attempt, self.case_id)
        attempt = self.root / "attempt2"
        self.count = 9
        capture.capture_saved(attempt_root=attempt, authority_root=self.authority,
                              site=self.site, case_suffix="two_cycles_failed_detection",
                              actor_id=23, observed_blueprint_id="vehicle.bicycle.test",
                              policy_receipt=self.policy, sample_tick=self.tick,
                              native_exit_code=0,
                              frame_count=9, diagnostic_fixture=True)
        receipt_path = attempt / "attempt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["camera_sources"].pop("driver_reference")
        receipt_path.write_text(json.dumps(receipt) + "\n")
        with self.assertRaisesRegex(ValueError, "four original camera sources missing"):
            media.audit_saved_media(attempt, self.case_id)
        with self.assertRaisesRegex(saved.SavedAttemptError, "four-camera media rejected"):
            saved.process_saved(attempt, self.authority, self.site, self.case_id,
                                allow_diagnostic=True)

    def test_reject_rehashed_camera_pixel_change(self):
        attempt = self.make()
        path = attempt / "camera-overview.zip"
        with ZipFile(path) as archive:
            members = [(name, archive.read(name)) for name in archive.namelist()]
        with ZipFile(path, "w") as archive:
            for index, (name, payload) in enumerate(members):
                archive.writestr(name, self.png[:-1] + b"0" if index == 0 else payload)
        receipt_path = attempt / "attempt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["camera_sources"]["overview"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        receipt_path.write_text(json.dumps(receipt) + "\n")
        with self.assertRaisesRegex(ValueError, "pixel binding differs"):
            media.audit_saved_media(attempt, self.case_id)

    def test_failed_tick_does_not_seal_completed_attempt(self):
        def bad_tick(index):
            row, images = self.tick(index)
            if index == 3:
                images.pop("driver_reference")
            return row, images
        self.count = 9
        attempt = self.root / "failed"
        with self.assertRaisesRegex(ValueError, "four-camera"):
            capture.capture_saved(attempt_root=attempt, authority_root=self.authority,
                                  site=self.site, case_suffix="two_cycles_failed_detection",
                                  actor_id=23, observed_blueprint_id="vehicle.bicycle.test",
                                  policy_receipt=self.policy, sample_tick=bad_tick,
                                  native_exit_code=0,
                                  frame_count=9, diagnostic_fixture=True)
        self.assertFalse((attempt / "attempt.json").exists())

    def test_failed_native_completion_does_not_seal_attempt(self):
        self.count = 9
        attempt = self.root / "native-failed"
        with self.assertRaisesRegex(ValueError, "Native completion failed"):
            capture.capture_saved(attempt_root=attempt, authority_root=self.authority,
                                  site=self.site, case_suffix="two_cycles_failed_detection",
                                  actor_id=23, observed_blueprint_id="vehicle.bicycle.test",
                                  policy_receipt=self.policy, sample_tick=self.tick,
                                  native_exit_code=1, frame_count=9, diagnostic_fixture=True)
        self.assertFalse(attempt.exists())


if __name__ == "__main__":
    unittest.main()
