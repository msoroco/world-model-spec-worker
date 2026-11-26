import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("delivery_audit", ROOT / "delivery_audit.py")
audit = importlib.util.module_from_spec(spec)
import sys
sys.path.insert(0, str(ROOT))
spec.loader.exec_module(audit)
SCRATCH = ROOT.parents[2] / ".runtime-work" / "c405647-delivery-audit-tests"


class DeliveryAuditTest(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = next(iter(audit.CASES))

    def test_rejects_synthetic_diagnostic(self):
        with self.assertRaisesRegex(ValueError, "Original Native delivery required"):
            audit.audit_structure(self.root, {"case_id": self.case,
                                              "source_kind": "synthetic_cpu_fixture"})

    def test_rejects_missing_original_inventory(self):
        with self.assertRaisesRegex(ValueError, "Original source inventory incomplete"):
            audit.audit_structure(self.root, {"case_id": self.case,
                                              "source_kind": "original_native_observation",
                                              "source_sha256": {}})

    def test_rejects_escaping_source(self):
        with self.assertRaisesRegex(ValueError, "Missing or escaping original source"):
            audit.within(self.root, "../other")

    def test_rejects_changed_source_hash(self):
        inventory = {name: "0" * 64 for name in
                     ("result.json", "video_frames.jsonl", "emergency_observations.jsonl",
                      "trace.json", "primary.mkv", "pixel-review.json",
                      *(view + ".mkv" for view in audit.VIEWS))}
        for name in inventory:
            (self.root / name).write_text("source")
        with self.assertRaisesRegex(ValueError, "Original source hash changed"):
            audit.audit_structure(self.root, {"case_id": self.case,
                                              "source_kind": "original_native_observation",
                                              "source_sha256": inventory})
