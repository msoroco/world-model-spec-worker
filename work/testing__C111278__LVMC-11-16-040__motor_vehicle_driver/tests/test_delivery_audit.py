import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from delivery_audit import CAMERAS, DeliveryError, audit

SHA = "a" * 64


class DeliveryTests(unittest.TestCase):
    def test_positive_and_missing_source_negative(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            streams = {}
            for name in CAMERAS:
                data = name.encode()
                (root / name).write_bytes(data)
                streams[name] = {"path": name, "sha256": hashlib.sha256(data).hexdigest()}
            receipt = dict(case_id="case", map_hash=SHA, recorded_only=True,
                           capture_kind="original_native", fps=20, duration_s=45,
                           streams=streams, frame_ids=list(range(900)), candidate="primary")
            measure = dict(case_id="case", map_hash=SHA, approach_frame_ids=[0, 1],
                           traversal_frame_ids=[2], source_sha256={"frames": SHA})
            self.assertEqual(audit(receipt, measure, root, "case")["recorded_only_join"], "passed")
            (root / "overview").unlink()
            with self.assertRaises(DeliveryError): audit(receipt, measure, root, "case")

    def test_rejects_unrecorded_and_frame_mismatch(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            streams = {}
            for name in CAMERAS:
                (root / name).write_text(name)
                streams[name] = {"path": name, "sha256": hashlib.sha256(name.encode()).hexdigest()}
            receipt = dict(case_id="case", map_hash=SHA, recorded_only=False,
                           capture_kind="original_native", fps=20, duration_s=45,
                           streams=streams, frame_ids=list(range(900)), candidate="primary")
            measure = dict(case_id="case", map_hash=SHA, approach_frame_ids=[0],
                           traversal_frame_ids=[901], source_sha256={"frames": SHA})
            with self.assertRaises(DeliveryError): audit(receipt, measure, root, "case")
            receipt["recorded_only"] = True
            with self.assertRaises(DeliveryError): audit(receipt, measure, root, "case")


if __name__ == "__main__": unittest.main()
