import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("c227824_comparison_delivery",
                                           ROOT / "comparison_delivery.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ComparisonDeliveryTests(unittest.TestCase):
    def test_rejects_diagnostic_pair_even_if_delivery_stub_claims_a_seal(self):
        paired = {"case_ids": ["left", "right"], "diagnostic_fixture": True,
                  "fixed_source_conditions_checked": ["map_sha256"],
                  "deliberate_difference_checked": "entry_request",
                  "source_sha256": {"left": {}, "right": {}}}
        with patch.object(MODULE, "audit_delivery",
                          side_effect=[{"case_id": "left", "native_seal_verified": True,
                                        "source_hashes_verified": True},
                                       {"case_id": "right", "native_seal_verified": True,
                                        "source_hashes_verified": True}]), \
                patch.object(MODULE, "audit_attempts", return_value=paired):
            with self.assertRaisesRegex(ValueError, "diagnostic comparison"):
                MODULE.audit("left", "right", "entry_vs_wait", "plan")

    def test_rejects_case_binding_mismatch_after_native_audit(self):
        paired = {"case_ids": ["left", "other"], "diagnostic_fixture": False}
        with patch.object(MODULE, "audit_delivery",
                          side_effect=[{"case_id": "left"}, {"case_id": "right"}]), \
                patch.object(MODULE, "audit_attempts", return_value=paired):
            with self.assertRaisesRegex(ValueError, "case identities differ"):
                MODULE.audit("left", "right", "entry_vs_wait", "plan")


if __name__ == "__main__":
    unittest.main()
