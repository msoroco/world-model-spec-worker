import hashlib
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


MODULE = Path(__file__).resolve().parents[1] / "delivery_audit.py"
spec = importlib.util.spec_from_file_location("delivery_audit", MODULE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def fixture(root):
    sources = {}
    for name in ("native_result", "frame_map", *audit.CAMERAS):
        data = (name + " synthetic source").encode()
        (root / name).write_bytes(data)
        sources[name] = {"path": name, "sha256": hashlib.sha256(data).hexdigest()}
    packet = {"case_id": "exact-case", "fps": 20, "frame_count": 3,
              "native_result_sha256": sources["native_result"]["sha256"],
              "frame_map_sha256": sources["frame_map"]["sha256"], "sources": sources}
    measurement = {"case_id": "exact-case", "legal_practicability": "unresolved",
                   "fixed_sources": {"obstacle_source_sha256": "obs", "participant_source_sha256": "people",
                                     "pedestrian_source_sha256": "walker-source"},
                   "full_original_trace": [{"frame": n, "within_crosswalk": n == 1,
                                            "pedestrian_id": "walker-1", "pedestrian_source": "walker-source",
                                            "obstacle_source": "obs", "participant_source": "people",
                                            "available_right_width_m": 0.5, "nearby_participants": []}
                                           for n in range(3)]}
    return packet, measurement


class SavedAuditTest(unittest.TestCase):
    def test_positive_and_missing_camera(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet, measurement = fixture(root)
            self.assertTrue(audit.audit_saved(packet, measurement, root)["passed"])
            del packet["sources"]["approach"]
            with self.assertRaisesRegex(ValueError, "missing saved source"):
                audit.audit_saved(packet, measurement, root)

    def test_stale_source_and_unsafe_path(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet, measurement = fixture(root)
            (root / "overview").write_text("changed")
            with self.assertRaisesRegex(ValueError, "hash differs"):
                audit.audit_saved(packet, measurement, root)
            packet["sources"]["overview"]["path"] = "../outside"
            with self.assertRaisesRegex(ValueError, "escapes attempt"):
                audit.audit_saved(packet, measurement, root)

    def test_missing_context_and_no_passage(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet, measurement = fixture(root)
            measurement["full_original_trace"][1]["within_crosswalk"] = False
            with self.assertRaisesRegex(ValueError, "no observed crosswalk"):
                audit.audit_saved(packet, measurement, root)
            measurement["full_original_trace"][1]["within_crosswalk"] = True
            measurement["full_original_trace"][1].pop("nearby_participants")
            with self.assertRaisesRegex(ValueError, "missing practicability context"):
                audit.audit_saved(packet, measurement, root)

    def test_no_legal_verdict_or_broken_frames(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet, measurement = fixture(root)
            measurement["legal_practicability"] = "compliant"
            with self.assertRaisesRegex(ValueError, "unsupported practicability"):
                audit.audit_saved(packet, measurement, root)
            measurement["legal_practicability"] = "unresolved"
            measurement["full_original_trace"][2]["frame"] = 4
            with self.assertRaisesRegex(ValueError, "gapped original"):
                audit.audit_saved(packet, measurement, root)

    def test_pedestrian_identity_join(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            packet, measurement = fixture(root)
            measurement["full_original_trace"][1]["pedestrian_id"] = "other-walker"
            with self.assertRaisesRegex(ValueError, "pedestrian identity"):
                audit.audit_saved(packet, measurement, root)


if __name__ == "__main__":
    unittest.main()
