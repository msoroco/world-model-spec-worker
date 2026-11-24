import hashlib
import json
import pathlib
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import native_capture as native
from test_parked_lamps import site


class Vehicle:
    is_alive = True
    def __init__(self):
        self.destroyed = False
    def get_velocity(self):
        return types.SimpleNamespace(x=0.0, y=0.0, z=0.0)
    def get_control(self):
        return types.SimpleNamespace(hand_brake=True)
    def get_transform(self):
        return types.SimpleNamespace(location=types.SimpleNamespace(x=1.0, y=2.0, z=0.0),
                                     rotation=types.SimpleNamespace(yaw=0.0))
    def get_light_state(self):
        return 3
    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self, gap=False):
        self.frame = 100
        self.gap = gap
    def tick(self):
        value = self.frame
        self.frame += 2 if self.gap and value == 125 else 1
        return value
    def get_snapshot(self):
        return types.SimpleNamespace(frame=self.frame - 1,
            timestamp=types.SimpleNamespace(elapsed_seconds=(self.frame - 101) / 20))


def source_packet(root):
    s = site()
    s["case_id"] = native.ASSIGNMENT + "__dark_lamps_on"
    s["installed_lamp_positions"] = [{"side": "left", "source": "source document"}]
    s["camera_transforms"] = {name: {"xyz": [1.0, 2.0, 3.0],
                                     "rpy": [0.0, 0.0, 0.0], "source": "source document"}
                              for name in native.NAMES}
    evidence = dict(s)
    source = root / "independent-source.json"
    source.write_text(json.dumps(evidence, sort_keys=True))
    s["site_source_path"] = str(source)
    s["site_source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    packet = root / "site-input.json"
    packet.write_text(json.dumps(s, sort_keys=True))
    return packet


def images(frame):
    return {name: {"frame": frame, "source_sensor": "native-" + name,
                   "bytes": b"\x89PNG\r\n\x1a\n" + name.encode() + str(frame).encode()}
            for name in native.NAMES}


class CaptureTest(unittest.TestCase):
    def test_full_source_join_and_saved_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            source = source_packet(root)
            out = root / "attempt"
            out.mkdir()
            vehicle = Vehicle()
            with patch.object(native, "construct", return_value={"actor": vehicle, "requested_lamp_mask": 3}):
                result = native.capture(World(), source, "dark_lamps_on", out, images)
            self.assertEqual(result["native_last_frame"], 999)
            self.assertTrue(vehicle.destroyed)
            from encode_original import original_rows
            mapping, trace = original_rows(out)
            self.assertEqual(len(mapping), 900)
            self.assertEqual((mapping[0]["carla_frame"], mapping[-1]["carla_frame"]), (100, 999))
            self.assertEqual(trace[0]["position_m"], [1.0, 2.0, 0.0])
            from parked_lamps import audit_saved_capture
            self.assertEqual(len(audit_saved_capture(out, "dark_lamps_on", "a" * 64)["camera_names"]), 4)
            (out / "cameras" / "rear" / "0088.png").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "rear original image changed"):
                audit_saved_capture(out, "dark_lamps_on", "a" * 64)

    def test_rejects_changed_independent_site_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            source = source_packet(root)
            (root / "independent-source.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "independent site document changed"):
                native.read_site(source, "dark_lamps_on")

    def test_rejects_camera_frame_mismatch_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            source = source_packet(root)
            out = root / "attempt"
            out.mkdir()
            vehicle = Vehicle()
            def wrong(frame):
                value = images(frame)
                value["rear"]["frame"] += 1
                return value
            with patch.object(native, "construct", return_value={"actor": vehicle, "requested_lamp_mask": 3}):
                with self.assertRaisesRegex(ValueError, "rear original camera frame mismatch"):
                    native.capture(World(), source, "dark_lamps_on", out, wrong)
            self.assertTrue(vehicle.destroyed)
            self.assertFalse((out / "capture-packet.json").exists())

    def test_rejects_frame_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            source = source_packet(root)
            out = root / "attempt"
            out.mkdir()
            vehicle = Vehicle()
            with patch.object(native, "construct", return_value={"actor": vehicle, "requested_lamp_mask": 3}):
                with self.assertRaisesRegex(ValueError, "Native frame gap|snapshot mismatch"):
                    native.capture(World(gap=True), source, "dark_lamps_on", out, images)
            self.assertTrue(vehicle.destroyed)
            self.assertFalse((out / "capture-packet.json").exists())

    def test_rejects_camera_sensor_switch_during_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            source = source_packet(root)
            out = root / "attempt"
            out.mkdir()
            vehicle = Vehicle()
            def switched(frame):
                value = images(frame)
                if frame >= 110:
                    value["rear"]["source_sensor"] = "replacement-rear"
                return value
            with patch.object(native, "construct", return_value={"actor": vehicle, "requested_lamp_mask": 3}):
                with self.assertRaisesRegex(ValueError, "sensor identity changed"):
                    native.capture(World(), source, "dark_lamps_on", out, switched)
            self.assertTrue(vehicle.destroyed)
            self.assertFalse((out / "capture-packet.json").exists())

    def test_saved_audit_rejects_resealed_sensor_or_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            source = source_packet(root)
            out = root / "attempt"
            out.mkdir()
            with patch.object(native, "construct", return_value={"actor": Vehicle(), "requested_lamp_mask": 3}):
                native.capture(World(), source, "dark_lamps_on", out, images)
            from parked_lamps import audit_saved_capture
            mapping_path = out / "original_frame_map.json"
            packet_path = out / "capture-packet.json"
            mapping = json.loads(mapping_path.read_text())
            packet = json.loads(packet_path.read_text())
            mapping["frames"][5]["sources"]["rear"]["sensor"] = "replacement-rear"
            mapping_path.write_text(json.dumps(mapping))
            packet["original_frame_map_sha256"] = hashlib.sha256(mapping_path.read_bytes()).hexdigest()
            packet_path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "rear original camera sensor identity mismatch"):
                audit_saved_capture(out, "dark_lamps_on", "a" * 64)
            mapping["frames"][5]["sources"]["rear"]["sensor"] = "native-rear"
            mapping["frames"][5]["sources"]["rear"]["sha256"] = "0" * 64
            mapping_path.write_text(json.dumps(mapping))
            packet["original_frame_map_sha256"] = hashlib.sha256(mapping_path.read_bytes()).hexdigest()
            packet_path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "rear original camera image hash join mismatch"):
                audit_saved_capture(out, "dark_lamps_on", "a" * 64)

    def test_saved_entrypoint_uses_original_source_and_rejects_missing_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            source = source_packet(root)
            attempt = root / "attempt"
            capture = attempt / "capture"
            capture.mkdir(parents=True)
            with patch.object(native, "construct", return_value={"actor": Vehicle(), "requested_lamp_mask": 3}):
                native.capture(World(), source, "dark_lamps_on", capture, images)
            (attempt / "config.json").write_text(json.dumps({
                "selected_case_id": native.ASSIGNMENT + "__dark_lamps_on", "case_key": "dark_lamps_on"}))
            import finalize_original
            report = root / "report.json"
            with patch.object(sys, "argv", ["finalize_original.py", "--attempt", str(attempt),
                                            "--output", str(report)]):
                finalize_original.main()
            self.assertEqual(json.loads(report.read_text())["measurements"]["parked_position"]["value"]["frame_count"], 900)
            (capture / "site_packet.json").unlink()
            with patch.object(sys, "argv", ["finalize_original.py", "--attempt", str(attempt),
                                            "--output", str(report)]):
                with self.assertRaisesRegex(ValueError, "Missing required source: capture/site_packet.json"):
                    finalize_original.main()


if __name__ == "__main__":
    unittest.main()
