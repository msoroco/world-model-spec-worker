import hashlib
import importlib.util
import pathlib
import tempfile
import unittest

from test_native_capture import CASE, SITE, callbacks


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CAPTURE = load("native_capture")
AUDIT = load("delivery_audit")


class DeliveryAuditTests(unittest.TestCase):
    def test_source_join_and_external_seal(self):
        with tempfile.TemporaryDirectory() as tmp:
            tick, sample, camera_png = callbacks()
            CAPTURE.capture_attempt(tmp, case_id=CASE, site=SITE,
                                    tick=tick, sample=sample, camera_png=camera_png)
            packet_path = pathlib.Path(tmp) / "encounter-packet.json"
            digest = hashlib.sha256(packet_path.read_bytes()).hexdigest()
            result = AUDIT.audit_saved(tmp, case_id=CASE, packet_sha256=digest)
            self.assertEqual(result["decoded_original_images"], 3600)
            self.assertEqual(result["original_frames"], 900)
            self.assertFalse(result["physical_completion"])
            with self.assertRaisesRegex(ValueError, "hash drift"):
                AUDIT.audit_saved(tmp, case_id=CASE, packet_sha256="0" * 64)
            with self.assertRaisesRegex(ValueError, "exact delivery case"):
                AUDIT.audit_saved(tmp, case_id=CASE + "_other", packet_sha256=digest)
            with self.assertRaisesRegex(ValueError, "reviewed original Native"):
                AUDIT.audit_saved(tmp, case_id=CASE, packet_sha256=digest,
                                  require_attested=True)


if __name__ == "__main__":
    unittest.main()
