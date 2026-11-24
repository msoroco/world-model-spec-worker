"""Source-byte and identity proof for the reviewed local Native handoff."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_handoff import validate_handoff
from runner import _controller


CASE = ("testing__C109035__NRS-484D-400-5__emergency_vehicle_driver"
        "__response_siren_pedestrian")


class NativeHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="c109035-handoff-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        cameras = []
        for name, width, height in (("overview", 1920, 1080),
                                    ("approach", 1280, 720),
                                    ("reference_corner", 1280, 720),
                                    ("driver_reference", 1280, 720)):
            cameras.append({"name": name, "width": width, "height": height,
                            "attachment": "world", "reviewer": "CPU fixture",
                            "pose_source_citation": "synthetic geometry",
                            "fov_deg": 90, "location_xyz_m": [0, 0, 4],
                            "rotation_rpy_deg": [0, 0, 0]})
        sources = {
            "site_packet": {"source_kind": "site_packet", "cameras": cameras},
            "dispatch_context": {"source_kind": "dispatch_context",
                                 "source_status": "documented", "event": "emergency_call",
                                 "event_interval_frames": [0, 899]},
            "equipment_record": {"source_kind": "equipment_record",
                                 "authorization_source": "synthetic document",
                                 "device_installation_source": "synthetic document"},
        }
        inventory = {}
        for name, value in sources.items():
            value.update(case_id=CASE, reviewer="CPU fixture",
                         source_citation="synthetic source")
            path = self.root / (name + ".json")
            path.write_text(json.dumps(value) + "\n")
            inventory[name] = {"path": str(path),
                               "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        log = self.root / "instrument.jsonl"
        with log.open("w") as stream:
            for frame in range(900):
                stream.write(json.dumps({
                    "case_id": CASE, "native_frame": frame,
                    "sample_id": "sample-" + str(frame),
                    "source_type": "independent_instrument",
                    "source_citation": "synthetic source",
                    "siren_active": False, "warning_lamp_active": False,
                }) + "\n")
        inventory["instrument_log"] = {
            "path": str(log), "sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
            "source_type": "independent_instrument",
            "source_citation": "synthetic source"}
        self.packet = self.root / "handoff.json"
        self.packet.write_text(json.dumps({
            "format": "c109035-reviewed-native-handoff-v1", "case_id": CASE,
            "cell_id": "C109035", "reviewer": "CPU fixture",
            "physical_acceptance_claimed": False, "sources": inventory,
        }) + "\n")

    def test_exact_source_bytes_and_roles(self):
        result = validate_handoff(self.packet, case_id=CASE)
        self.assertEqual(result["case_id"], CASE)
        self.assertFalse(result["physical_acceptance_claimed"])

    def test_missing_site_is_rejected(self):
        (self.root / "site_packet.json").unlink()
        with self.assertRaisesRegex(ValueError, "missing or symlinked"):
            validate_handoff(self.packet, case_id=CASE)

    def test_changed_source_bytes_are_rejected(self):
        with (self.root / "dispatch_context.json").open("a") as stream:
            stream.write("\n")
        with self.assertRaisesRegex(ValueError, "bytes differ"):
            validate_handoff(self.packet, case_id=CASE)

    def test_instrument_command_echo_is_rejected(self):
        path = self.root / "instrument.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[-1]["siren_commanded"] = True
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        packet = json.loads(self.packet.read_text())
        packet["sources"]["instrument_log"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.packet.write_text(json.dumps(packet) + "\n")
        with self.assertRaisesRegex(ValueError, "command echo"):
            validate_handoff(self.packet, case_id=CASE)

    def test_physical_control_requires_reviewed_exact_bytes(self):
        path = self.root / "local_control.py"
        path.write_text("def set_state(*args, **kwargs):\n    return None\n"
                        "def drive_step(*args, **kwargs):\n    return None\n")
        site = {"device_controller_reviewer": "CPU fixture",
                "device_controller_source_citation": "synthetic adapter",
                "device_controller_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        self.assertTrue(callable(_controller(site, path).drive_step))
        path.write_text(path.read_text() + "# changed\n")
        with self.assertRaisesRegex(ValueError, "bytes differ"):
            _controller(site, path)


if __name__ == "__main__":
    unittest.main()
