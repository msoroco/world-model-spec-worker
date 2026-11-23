import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


MODULE = Path(__file__).resolve().parents[1] / "saved_audit.py"
spec = importlib.util.spec_from_file_location("zone_saved_audit", MODULE)
audit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)


def rows():
    return [{"case_id": "load_prompt", "original_frame": 1000 + i, "elapsed_s": i / 20,
             "ego_id": "ego", "passenger_id": "passenger", "map_sha256": "map",
             "zone_source_sha256": "zone", "regulations_source_sha256": "reg",
             "clock_source_sha256": "clock", "camera_plan_sha256": "cameras",
             "source_sha256": "packet", "control_source_sha256": "control",
             "passenger_event": "boarding_started" if i == 20 else None,
             "passenger_event_source_sha256": "event" if i == 20 else None} for i in range(900)]


def run(data, declared_hash=None):
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "history.jsonl"
        raw = "".join(json.dumps(row, sort_keys=True) + "\n" for row in data).encode()
        path.write_bytes(raw)
        return audit.audit_original_history(path, declared_hash or hashlib.sha256(raw).hexdigest(),
                                            "load_prompt", "zone", "reg")


class SavedAuditTests(unittest.TestCase):
    def test_valid_original_history(self):
        result = run(rows())
        self.assertEqual(result["frame_count"], 900)
        self.assertFalse(result["physical_visibility_verified"])

    def test_rejects_stale_digest(self):
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            run(rows(), "0" * 64)

    def test_rejects_source_and_frame_tamper(self):
        for change in (lambda r: r[200].update(zone_source_sha256="wrong"),
                       lambda r: r[300].update(original_frame=1299),
                       lambda r: r[20].update(passenger_event_source_sha256="")):
            data = rows()
            change(data)
            with self.assertRaises(ValueError):
                run(data)


if __name__ == "__main__":
    unittest.main()
