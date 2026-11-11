import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from delivery_audit import CAMERAS, audit_attempt
from lane_finalizer import analyze
from test_lane_finalizer import write_sources


class LaneDeliveryAuditTests(unittest.TestCase):
    def test_recomputes_and_rejects_missing_or_changed_originals(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_sources(root)
            for name in CAMERAS:
                (root / (name + ".mkv")).write_bytes(b"synthetic-camera-placeholder")
            report = analyze(root)
            decoder = lambda path, frames, **kwargs: {"frames": frames}
            receipt = audit_attempt(root, report, decoder=decoder)
            self.assertTrue(receipt["measurement_recomputed"])
            self.assertEqual(len(receipt["camera_decodes"]), 4)
            self.assertFalse(receipt["physical_visibility_claimed"])
            bad = copy.deepcopy(report)
            bad["measurements"]["lane_boundary_observation"]["sources"][
                "marked_lane_sources.jsonl"] = "wrong"
            with self.assertRaisesRegex(ValueError, "source hash differs"):
                audit_attempt(root, bad, decoder=decoder)
            (root / "approach.mkv").unlink()
            with self.assertRaisesRegex(ValueError, "Missing named lane source camera"):
                audit_attempt(root, report, decoder=decoder)


if __name__ == "__main__":
    unittest.main()
