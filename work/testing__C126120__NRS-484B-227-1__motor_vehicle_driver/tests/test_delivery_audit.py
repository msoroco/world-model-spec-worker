import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analysis import build_report
from delivery_audit import audit, sha
import test_analysis as fixtures


class DeliveryAuditTests(unittest.TestCase):
    def test_rejects_unsealed_and_changed_originals(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixtures.SavedAnalysisTests().build_attempt(root)
            measured = build_report(root)["measurements"]["median_uturn_measurement"]["value"]
            fixtures.write(root/"result.json",{"measured_values":measured,
                "target_checks":[{"target":"realized multiple-movement U-turn",
                                  "measured":False,"matched":True},
                                 {"target":"full-body opening crossing without closed-divider contact",
                                  "measured":True,"matched":True}],
                "setup_confirmed":True,"behavior_attempted":True,"maneuver_completed":True})
            for name in ("overview","approach","reference_corner","driver_reference"):
                (root/(name+".mkv")).write_bytes(b"video")
            with self.assertRaisesRegex(FileNotFoundError,"capture-seal"):
                audit(root)
            sources={p.name:sha(p) for p in root.iterdir() if p.is_file()}
            fixtures.write(root/"capture-seal.json",{"format":"worker-sealed-capture",
                "provenance_kind":"native","diagnostic_fixture":False,
                "restoration":{"restored":True},"sources":sources})
            self.assertTrue(audit(root)["delivery_physical_audit_passed"])
            (root/"overview.mkv").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError,"sealed original source changed"):
                audit(root)


if __name__ == "__main__":
    unittest.main()
