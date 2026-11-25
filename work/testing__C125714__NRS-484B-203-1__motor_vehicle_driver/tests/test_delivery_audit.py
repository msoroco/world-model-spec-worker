"""Fail-closed original review and full saved video decode checks."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT.parents[1] / ".runtime-work" / "c125714-2031" / "audit-tests"
sys.path.insert(0, str(ROOT))
from delivery_audit import audit, decoded_frames


class DeliveryAuditTests(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "attempt"
        source = ROOT.parents[1] / ".runtime-work" / "c125714-2031" / "delivery-probe" / "right_half" / "positive" / "attempt"
        if not source.exists():
            self.skipTest("diagnostic delivery source has not been built")
        shutil.copytree(source, self.root)
        self.case = ROOT.name + "__right_half"

    def test_diagnostic_cannot_claim_physical_acceptance(self):
        result = audit(self.root, self.case, diagnostic=True)
        self.assertFalse(result["physical_acceptance_claimed"])

    def test_original_source_review_required_even_with_native_label(self):
        provenance_path = self.root / "acquisition-provenance.json"
        provenance = json.loads(provenance_path.read_text())
        provenance["provenance_kind"] = "native"
        provenance_path.write_text(json.dumps(provenance) + "\n")
        trace_path = self.root / "opposing-actor-trace.json"
        trace = json.loads(trace_path.read_text())
        trace["diagnostic_fixture"] = False
        trace_path.write_text(json.dumps(trace) + "\n")
        receipt_path = self.root / "opposing-capture-receipt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["sha256"] = hashlib.sha256(trace_path.read_bytes()).hexdigest()
        receipt_path.write_text(json.dumps(receipt) + "\n")
        with self.assertRaisesRegex(ValueError, "missing saved source: original-source-review.json"):
            audit(self.root, self.case)

    def test_full_decode_rejects_corrupt_frame_payload(self):
        video = self.root / "overview.mkv"
        data = video.read_bytes()
        video.write_bytes(b"corrupt video header" + data[20:])
        with self.assertRaises((ValueError, RuntimeError)):
            decoded_frames(video)


if __name__ == "__main__":
    unittest.main()
