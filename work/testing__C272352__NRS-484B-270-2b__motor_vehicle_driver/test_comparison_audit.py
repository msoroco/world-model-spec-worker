import json
import unittest
from pathlib import Path

from comparison_audit import assess


HERE = Path(__file__).resolve().parent


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads((HERE / "case-plan.json").read_text())

    def records(self, comparison):
        ids = next(x["case_ids"] for x in self.plan["comparisons"]
                   if x["comparison_id"] == comparison)
        return {ident: {"case_id": ident, "frame_count": 900,
                        "full_decode": True, "actual_pixels": True,
                        "physical_status": "unverified", "legal_verdict": None,
                        "native_map_sha256": "a" * 64,
                        "receipt_sha256": f"{index + 1:064x}",
                        "measurements": {"pass_geometry": {"value": {"minimum_body_gap_m": 1.2}}}}
                for index, ident in enumerate(ids)}

    def test_four_controlled_comparisons(self):
        for comparison in ("three_foot_clearance", "return_right_order",
                           "participant_alternatives", "special_route_authorizations"):
            with self.subTest(comparison=comparison):
                result = assess(comparison, self.records(comparison), diagnostic=True)
                self.assertFalse(result["source_verified"])
                self.assertIsNone(result["legal_verdict"])

    def test_reject_changed_fixed_site_and_reused_receipt(self):
        records = self.records("three_foot_clearance")
        ids = list(records)
        records[ids[1]]["native_map_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "fixed Native map"):
            assess("three_foot_clearance", records, diagnostic=True)
        records[ids[1]]["native_map_sha256"] = "a" * 64
        records[ids[1]]["receipt_sha256"] = records[ids[0]]["receipt_sha256"]
        with self.assertRaisesRegex(ValueError, "receipt reused"):
            assess("three_foot_clearance", records, diagnostic=True)

    def test_reject_missing_decode_and_measurement(self):
        records = self.records("return_right_order")
        ident = next(iter(records))
        records[ident]["full_decode"] = False
        with self.assertRaisesRegex(ValueError, "decode"):
            assess("return_right_order", records, diagnostic=True)
        records[ident]["full_decode"] = True
        records[ident]["measurements"] = {}
        with self.assertRaisesRegex(ValueError, "measurement"):
            assess("return_right_order", records, diagnostic=True)


if __name__ == "__main__":
    unittest.main()
