import copy
import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "rail_stop_audit.py"
SPEC = importlib.util.spec_from_file_location("rail_stop_audit", MODULE)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def packet():
    sources = {k: {"path": f"capture/{k}.json", "sha256": "a" * 64} for k in AUDIT.REQUIRED_SOURCES}
    context = {"crossing_type": "highway_railroad_grade", "designation_authority": "state_dot",
               "device_type": "official_stop_sign", "device_governs": "railroad_approach", "actor": "motor_vehicle_driver"}
    samples = []
    for frame, speed, y in [(100, 3, 10), (101, 0, 8), (102, 1, 7), (103, 2, 0)]:
        samples.append({"frame": frame, "elapsed_s": frame / 20, "speed_mps": speed,
                        "body_corners_xy_m": [[0, y], [1, y], [1, y + 1], [0, y + 1]],
                        "source_frame": f"native-{frame}"})
    return {"sources": sources, "context": context, "nearest_track_rails": [{"a": [0, 0], "b": [1, 0]}], "samples": samples}


class RailStopAuditTest(unittest.TestCase):
    def test_saved_file_checks_source_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            p = packet()
            for key, binding in p["sources"].items():
                source = root / binding["path"]
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text(key)
                binding["sha256"] = hashlib.sha256(key.encode()).hexdigest()
            packet_path = root / "packet.json"
            packet_path.write_text(json.dumps(p))
            self.assertTrue(AUDIT.audit_saved_file(packet_path)["complete_stop_observed"])
            (root / p["sources"]["native_stop_device"]["path"]).write_text("changed")
            with self.assertRaisesRegex(ValueError, "source hash differs"):
                AUDIT.audit_saved_file(packet_path)

    def test_saved_file_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            p = packet()
            p["sources"]["native_stop_device"]["path"] = "../other"
            packet_path = Path(directory) / "packet.json"
            packet_path.write_text(json.dumps(p))
            with self.assertRaisesRegex(ValueError, "unsafe source path"):
                AUDIT.audit_saved_file(packet_path)

    def test_complete_stop_and_proceeding(self):
        result = AUDIT.audit_saved_packet(packet())
        self.assertTrue(result["complete_stop_observed"])
        self.assertEqual(result["first_stop_frame"], 101)
        self.assertTrue(result["proceeding_observed"])
        self.assertAlmostEqual(result["first_stop_body_to_nearest_rail_min_ft"], 8 * AUDIT.FEET_PER_METRE)
        self.assertIn("independent", result["due_care"])

    def test_rolling_never_stopped(self):
        p = packet()
        p["samples"][1]["speed_mps"] = 0.1
        self.assertFalse(AUDIT.audit_saved_packet(p)["complete_stop_observed"])

    def test_stop_after_rail_contact_is_not_approach_stop(self):
        p = packet()
        p["samples"][1]["speed_mps"] = 1
        p["samples"][3]["speed_mps"] = 0
        self.assertFalse(AUDIT.audit_saved_packet(p)["complete_stop_observed"])

    def test_missing_source_rejected(self):
        p = packet()
        del p["sources"]["native_authority_record"]
        with self.assertRaisesRegex(ValueError, "native_authority_record"):
            AUDIT.audit_saved_packet(p)

    def test_local_authority_requires_approval_source(self):
        p = packet()
        p["context"]["designation_authority"] = "local_with_dot_approval"
        with self.assertRaisesRegex(ValueError, "DOT approval"):
            AUDIT.audit_saved_packet(p)

    def test_sign_must_govern_crossing(self):
        p = packet()
        p["context"]["device_governs"] = "nearby_intersection"
        with self.assertRaisesRegex(ValueError, "governance"):
            AUDIT.audit_saved_packet(p)

    def test_frame_gap_rejected(self):
        p = packet()
        p["samples"][2]["frame"] = 105
        with self.assertRaisesRegex(ValueError, "gap"):
            AUDIT.audit_saved_packet(p)

    def test_elapsed_mismatch_rejected(self):
        p = packet()
        p["samples"][2]["elapsed_s"] = 1
        with self.assertRaisesRegex(ValueError, "20 Hz"):
            AUDIT.audit_saved_packet(p)

    def test_missing_footprint_rejected(self):
        p = packet()
        p["samples"][1]["body_corners_xy_m"] = []
        with self.assertRaisesRegex(ValueError, "four original"):
            AUDIT.audit_saved_packet(p)

    def test_missing_original_frame_identity_rejected(self):
        p = packet()
        del p["samples"][1]["source_frame"]
        with self.assertRaisesRegex(ValueError, "source frame"):
            AUDIT.audit_saved_packet(p)


if __name__ == "__main__":
    unittest.main()
