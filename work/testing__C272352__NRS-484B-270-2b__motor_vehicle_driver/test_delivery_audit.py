import unittest

from delivery_audit import assess


AID = "testing__C272352__NRS-484B-270-2b__motor_vehicle_driver"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


class DeliveryAuditTests(unittest.TestCase):
    def setUp(self):
        self.case = AID + "__bike_clearance_above"
        self.capture = {"case_id": self.case, "frame_count": 900,
                        "full_decode": True, "receipt_sha256": "a" * 64,
                        "source_bindings": {name + ".mkv": "b" * 64
                                            for name in CAMERAS}}
        self.review = {"case_id": self.case,
                       "capture_receipt_sha256": "a" * 64,
                       "legal_due_care": None, "legal_safe_distance": None,
                       "legal_safely_clear": None, "legal_exception_213_217": None,
                       "views": {name: {"video_sha256": "b" * 64,
                                        "reviewer": "CPU protocol tester",
                                        "samples": [{"frame": 100, "ego_visible": True,
                                                     "qualifying_rider_visible": True,
                                                     "decoded_rgb_sha256": "c" * 64}]}
                                 for name in CAMERAS}}
        self.physical = {"case_id": self.case, "maneuver_completed": True,
                         "physical_checks": {"maneuver": {"status": "met",
                                                          "sources": {"trace": "d" * 64}}},
                         "realized_observables": {"path": 10}}

    def test_diagnostic_protocol_is_not_source_verified(self):
        result = assess(self.case, self.capture, self.review, self.physical,
                        diagnostic=True)
        self.assertFalse(result["source_verified"])
        self.assertFalse(result["canonical_acceptance"])

    def test_missing_pixel_and_physical_sources_rejected(self):
        self.review["views"]["overview"]["samples"][0]["qualifying_rider_visible"] = False
        with self.assertRaisesRegex(ValueError, "pixel review incomplete"):
            assess(self.case, self.capture, self.review, self.physical, diagnostic=True)
        self.review["views"]["overview"]["samples"][0]["qualifying_rider_visible"] = True
        self.physical["physical_checks"]["maneuver"]["sources"] = {}
        with self.assertRaisesRegex(ValueError, "physical completion missing"):
            assess(self.case, self.capture, self.review, self.physical, diagnostic=True)


if __name__ == "__main__":
    unittest.main()
