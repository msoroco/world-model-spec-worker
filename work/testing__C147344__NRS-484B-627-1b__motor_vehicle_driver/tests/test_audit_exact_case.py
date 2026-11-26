"""The queue's exact case must be bound to its source audit receipt."""
import unittest
from pathlib import Path
from unittest.mock import patch

from audit_exact_case import audit_case
from reviewed_scene import ASSIGNMENT


class ExactCaseAuditTests(unittest.TestCase):
    def test_mismatched_receipt_rejected_before_source_dispatch(self):
        selected = ASSIGNMENT + "__slow_middle_follower"
        with patch("audit_exact_case.delivery_audit.audit") as source_audit:
            with self.assertRaisesRegex(ValueError, "does not match"):
                audit_case(selected, Path("/source"), {"case_id": ASSIGNMENT + "__normal_follow"})
            source_audit.assert_not_called()

    def test_unsupported_case_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside this assignment"):
            audit_case(ASSIGNMENT + "__invented", Path("/source"),
                       {"case_id": ASSIGNMENT + "__invented"})

    def test_original_dispatch(self):
        case = ASSIGNMENT + "__slow_middle_follower"
        with patch("audit_exact_case.delivery_audit.audit", return_value={"case_id": case}) as source_audit:
            self.assertEqual(audit_case(case, Path("/source"), {"case_id": case}), {"case_id": case})
            source_audit.assert_called_once()

    def test_engineering_dispatch(self):
        case = ASSIGNMENT + "__impediment-0000"
        with patch("audit_exact_case.engineering_delivery_audit.audit", return_value={"case_id": case}) as source_audit:
            self.assertEqual(audit_case(case, Path("/source"), {"case_id": case}), {"case_id": case})
            source_audit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
