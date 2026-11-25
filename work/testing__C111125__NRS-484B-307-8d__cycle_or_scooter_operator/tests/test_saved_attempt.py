import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("c111125_saved_attempt", ROOT / "saved_attempt.py")
saved = importlib.util.module_from_spec(spec)
spec.loader.exec_module(saved)


class SavedAttemptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.authority = self.root / "authority"
        self.attempt = self.root / "attempt"
        self.authority.mkdir()
        self.attempt.mkdir()
        self.site = {
            "cell_id": "C111125", "maneuver": "straight",
            "device_kind": "official_traffic_control_device",
            "ego_blueprint_class": "bicycle", "ego_blueprint_id": "vehicle.bicycle.test",
            "rider_model_id": "walker.rider.test", "device_id": "signal.1", "detector_id": "loop.1",
            "detector_controls_subject_signal": True,
            "approach_lane_id": 1, "cross_lane_id": 2,
            "stop_boundary_station_m": 1.0, "entry_station_m": 9.0,
        }
        packets = {
            "map": {k: self.site[k] for k in ("cell_id", "approach_lane_id", "cross_lane_id", "stop_boundary_station_m", "entry_station_m")},
            "device": {k: self.site[k] for k in ("device_id", "device_kind", "detector_id")},
            "detector": {"detector_id": self.site["detector_id"], "controls_device_id": self.site["device_id"], "zone_lane_id": self.site["approach_lane_id"]},
            "blueprint": {k: self.site[k] for k in ("ego_blueprint_id", "ego_blueprint_class", "rider_model_id")},
        }
        for name, data in packets.items():
            self.site[name + "_ref"] = self.ref(self.authority, name + ".json", data)
        self.case_id = saved.ASSIGNMENT_ID + "__two_cycles_failed_detection"
        self.build_attempt()

    def ref(self, root, name, data):
        path = root / name
        path.write_text(json.dumps(data, sort_keys=True) + "\n", encoding="utf-8")
        return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def build_attempt(self):
        phases = ["red", "green", "yellow", "red", "green", "yellow", "red", "red", "red"]
        frames = []
        for i, phase in enumerate(phases):
            station = 0.0 if i < 7 else (5.0 if i == 7 else 10.0)
            frames.append({"frame": i, "timestamp_s": i / 20,
                           "subject_signal": "red", "cross_signal": phase,
                           "detector_occupied": True, "detector_output": False,
                           "ego_speed_mps": 0.0 if station == 0 else 1.0,
                           "ego_station_m": station,
                           "directed_participant_conflict": False})
        stream = io.BytesIO()
        Image.new('RGB', (4, 3), color=(10, 20, 30)).save(stream, format='PNG')
        pixels = stream.getvalue()
        camera_sources = {}
        for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
            path = self.attempt / ('camera-' + name + '.zip')
            with ZipFile(path, 'w', compression=ZIP_STORED) as archive:
                for row in frames:
                    member = f'{row["frame"]:08d}.png'
                    archive.writestr(member, pixels)
                    row.setdefault('camera_frames', {})[name] = {
                        'member': member, 'sha256': hashlib.sha256(pixels).hexdigest()}
            camera_sources[name] = {'path': path.name,
                                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                    'frame_count': len(frames)}
        native = self.ref(self.attempt, "native.json", {"frames": frames, "blueprint_class": "bicycle"})
        device = self.ref(self.attempt, "device.json", {"frames": [
            {"frame": f["frame"], "subject_signal": f["subject_signal"], "cross_signal": f["cross_signal"]} for f in frames]})
        detector = self.ref(self.attempt, "detector.json", {"frames": [
            {"frame": f["frame"], "occupied": f["detector_occupied"], "output": f["detector_output"]} for f in frames]})
        geometry = self.ref(self.attempt, "geometry.json", {"stop_boundary_station_m": 1.0, "entry_station_m": 9.0})
        policy = {"device_sha256": self.site["device_ref"]["sha256"],
                  "detector_sha256": self.site["detector_ref"]["sha256"]}
        packet = {"case_suffix": "two_cycles_failed_detection", "blueprint_class": "bicycle",
                  "actor_id": 23, "observed_blueprint_id": "vehicle.bicycle.test",
                  "policy_receipt": policy,
                  "device_sha256": self.site["device_ref"]["sha256"],
                  "map_sha256": self.site["map_ref"]["sha256"], "frames": frames,
                  "native_trace_ref": native, "device_trace_ref": device,
                  "detector_trace_ref": detector, "geometry_ref": geometry}
        packet_ref = self.ref(self.attempt, "packet.json", packet)
        receipt = {"format": "c111125-native-attempt-v1", "case_id": self.case_id,
                   "diagnostic_fixture": True, "native_exit_code": 0,
                   "actor_id": 23, "observed_blueprint_id": "vehicle.bicycle.test",
                   "policy_receipt": policy, "packet_ref": packet_ref,
                   "frame_count": len(frames), 'camera_sources': camera_sources,
                   'camera_capture_complete': True}
        self.ref(self.attempt, "attempt.json", receipt)

    def test_diagnostic_source_join_and_delivery_rejection(self):
        with self.assertRaisesRegex(saved.SavedAttemptError, "diagnostic fixture"):
            saved.process_saved(self.attempt, self.authority, self.site, self.case_id)
        result = saved.process_saved(self.attempt, self.authority, self.site, self.case_id, allow_diagnostic=True)
        self.assertEqual(result["measurement"]["complete_device_cycles_before_entry"], 2)
        self.assertTrue(result["diagnostic_fixture"])
        self.assertFalse(result["physical_acceptance"])
        self.assertIsNone(result["legal_verdict"])

    def test_reject_changed_packet_and_original_stream(self):
        (self.attempt / "packet.json").write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(saved.SavedAttemptError, "hash mismatch"):
            saved.process_saved(self.attempt, self.authority, self.site, self.case_id, allow_diagnostic=True)
        self.build_attempt()
        (self.attempt / "native.json").write_text("{}\n", encoding="utf-8")
        with self.assertRaisesRegex(saved.SavedAttemptError, "hash mismatch"):
            saved.process_saved(self.attempt, self.authority, self.site, self.case_id, allow_diagnostic=True)

    def test_reject_identity_policy_and_frame_count(self):
        path = self.attempt / "attempt.json"
        original = json.loads(path.read_text())
        for change, message in (
            ({"case_id": saved.ASSIGNMENT_ID + "__one_cycle"}, "identity mismatch"),
            ({"observed_blueprint_id": "vehicle.car"}, "blueprint changed"),
            ({"frame_count": 8}, "frame count differs"),
            ({"native_exit_code": 1}, "Native completion"),
        ):
            with self.subTest(change=change):
                self.ref(self.attempt, "attempt.json", {**original, **change})
                with self.assertRaisesRegex(saved.SavedAttemptError, message):
                    saved.process_saved(self.attempt, self.authority, self.site, self.case_id, allow_diagnostic=True)
        self.ref(self.attempt, "attempt.json", original)
        packet = json.loads((self.attempt / "packet.json").read_text())
        packet["actor_id"] = 99
        receipt = {**original, "packet_ref": self.ref(self.attempt, "packet.json", packet)}
        self.ref(self.attempt, "attempt.json", receipt)
        with self.assertRaisesRegex(saved.SavedAttemptError, "actor readback"):
            saved.process_saved(self.attempt, self.authority, self.site, self.case_id, allow_diagnostic=True)

    def test_reject_path_escape(self):
        receipt = json.loads((self.attempt / "attempt.json").read_text())
        receipt["packet_ref"]["path"] = "../authority/map.json"
        self.ref(self.attempt, "attempt.json", receipt)
        with self.assertRaisesRegex(saved.SavedAttemptError, "outside attempt"):
            saved.process_saved(self.attempt, self.authority, self.site, self.case_id, allow_diagnostic=True)

    def test_saved_only_cli_keeps_output_outside_sealed_attempt(self):
        site_path = self.authority / "site.json"
        site_path.write_text(json.dumps(self.site) + "\n", encoding="utf-8")
        command = [sys.executable, str(ROOT / "saved_attempt.py"),
                   "--attempt", str(self.attempt), "--authority-root", str(self.authority),
                   "--site", str(site_path), "--case-id", self.case_id,
                   "--output", str(self.root / "measurement.json"), "--allow-diagnostic"]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue((self.root / "measurement.json").is_file())
        command[command.index(str(self.root / "measurement.json"))] = str(self.attempt / "measurement.json")
        rejected = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("separate from sealed attempt", rejected.stderr)
        self.assertFalse((self.attempt / "measurement.json").exists())


if __name__ == "__main__":
    unittest.main()
