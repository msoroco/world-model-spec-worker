"""CPU source-isolation tests for the property-route comparison audit."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from audit_property_comparison import audit
from property_bypass_measure import measure
from prove_property_bypass import sample


def encode(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def measured(via_property: bool) -> dict:
    frames, site, intent = sample(via_property=via_property)
    for source in (frames, site, intent):
        source["source_kind"] = "native_saved_sample"
    return measure(encode(frames), encode(site), encode(intent))


class ComparisonAuditTest(unittest.TestCase):
    def setUp(self):
        self.road = measured(False)
        self.property_route = measured(True)

    def test_fixed_sources_and_changed_path(self):
        receipt = audit(self.road, self.property_route)
        self.assertTrue(receipt["isolation_passed"])
        self.assertIsNone(receipt["legal_result"])

    def test_map_source_changed(self):
        self.property_route["map_inventory_sha256"] = "another-map"
        with self.assertRaisesRegex(ValueError, "map_inventory_sha256"):
            audit(self.road, self.property_route)

    def test_purpose_changed(self):
        self.property_route["declared_purpose"] = "other"
        with self.assertRaisesRegex(ValueError, "declared_purpose"):
            audit(self.road, self.property_route)

    def test_missing_original_source(self):
        self.property_route["source_kind"] = "synthetic_native_sample"
        with self.assertRaisesRegex(ValueError, "original saved Native"):
            audit(self.road, self.property_route)

    def test_road_entered_property(self):
        self.road["first_property_frame"] = 250
        with self.assertRaisesRegex(ValueError, "road-only control"):
            audit(self.road, self.property_route)

    def test_missing_signal_readback(self):
        self.property_route["cross_street_not_red_at_entry"] = None
        with self.assertRaisesRegex(ValueError, "signal observations"):
            audit(self.road, self.property_route)


if __name__ == "__main__":
    unittest.main()
