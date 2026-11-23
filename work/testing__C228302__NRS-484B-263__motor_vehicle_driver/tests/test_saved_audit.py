import importlib.util
import sys
import unittest
from pathlib import Path


module_path = Path(__file__).resolve().parents[1] / "saved_audit.py"
spec = importlib.util.spec_from_file_location("saved_audit", module_path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def packet():
    return {
        "case_id": "exit_yield_first", "native_result_sha256": "native-hash",
        "original_history_sha256": "history-hash", "frame_count": 900,
        "frame_map": [{"original_frame": 100 + i, "elapsed_s": i * .05} for i in range(900)],
        "videos": {name: {"sha256": "video-hash", "decode_receipt_sha256": "receipt-hash",
                          "decoded_frame_count": 900, "actual_pixel_audit": True,
                          "first_original_frame": 100, "last_original_frame": 999}
                   for name in ("chase", "overhead", "front", "side")},
        "measurement": {"case_id": "exit_yield_first", "frame_count": 900,
                        "source_history_sha256": "history-hash", "first_entry_frame": 120,
                        "approaching_actor_ids": [2], "immediate_hazard_judgment": None,
                        "reasonable_safety_judgment": None},
    }


class Tests(unittest.TestCase):
    def test_positive_packet(self):
        self.assertTrue(module.audit_saved(packet())["source_bound"])

    def test_reject_missing_camera(self):
        p = packet()
        del p["videos"]["front"]
        with self.assertRaisesRegex(ValueError, "four original cameras required"):
            module.audit_saved(p)

    def test_reject_stale_measurement(self):
        p = packet()
        p["measurement"]["source_history_sha256"] = "stale"
        with self.assertRaisesRegex(ValueError, "measurement source mismatch"):
            module.audit_saved(p)

    def test_reject_incomplete_decode(self):
        p = packet()
        p["videos"]["side"]["decoded_frame_count"] = 899
        with self.assertRaisesRegex(ValueError, "full camera decode missing"):
            module.audit_saved(p)

    def test_reject_legal_label(self):
        p = packet()
        p["measurement"]["reasonable_safety_judgment"] = True
        with self.assertRaisesRegex(ValueError, "worker may not assert legal judgment"):
            module.audit_saved(p)
