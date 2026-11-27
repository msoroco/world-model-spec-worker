"""Source-bound qualifying-context checks on invented CPU packets."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "native"))
from source_gate import FIELDS, audit


ASSIGNMENT = "training__C229398__LVMC-11-52-300__nonmotor_vehicle_operator"


class SourceGateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[3] /
                                                ".runtime-work")
        self.root = Path(self.temp.name)
        findings = {
            "transport_capability": True,
            "excluded_device": False,
            "self_propulsion": False,
            "responsible_person": "synthetic operator",
            "parking_purpose": "park",
            "active_loading_or_unloading": False,
            "street_public_access": True,
            "city_limits": True,
            "civil_clock": {"iana_timezone": "America/Los_Angeles",
                            "utc_start_ms": 1795444200000},
        }
        sources = {}
        for field in FIELDS:
            path = self.root / (field + ".json")
            path.write_text(json.dumps({"fixture": field, "finding": findings[field]}) + "\n")
            sources[field] = {"path": path.name,
                              "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                              "citation": "Synthetic CPU fixture for " + field,
                              "source_kind": "synthetic_cpu"}
        self.packet = self.root / "packet.json"
        self.data = {"format": "c229398-source-review-v1",
                     "case_id": ASSIGNMENT + "__above_30",
                     "source_kind": "synthetic_cpu", "findings": findings,
                     "sources": sources}
        self.save()

    def tearDown(self):
        self.temp.cleanup()

    def save(self):
        self.packet.write_text(json.dumps(self.data) + "\n")

    def test_positive_and_original_requirement(self):
        result = audit(self.packet)
        self.assertTrue(result["qualifying_context_supported"])
        self.assertFalse(result["physical_or_legal_acceptance"])
        with self.assertRaisesRegex(ValueError, "Original review required"):
            audit(self.packet, require_original=True)

    def test_device_motor_and_loading_negatives(self):
        self.data["findings"]["self_propulsion"] = True
        self.save()
        self.assertFalse(audit(self.packet)["qualifying_context_supported"])
        self.data["findings"]["self_propulsion"] = False
        self.data["findings"]["active_loading_or_unloading"] = True
        self.save()
        self.assertFalse(audit(self.packet)["qualifying_context_supported"])

    def test_missing_source_and_stale_hash(self):
        del self.data["sources"]["city_limits"]
        self.save()
        with self.assertRaisesRegex(ValueError, "Each finding needs"):
            audit(self.packet)
        self.data["sources"]["city_limits"] = {
            "path": "city_limits.json", "sha256": "0" * 64,
            "citation": "synthetic", "source_kind": "synthetic_cpu"}
        self.save()
        with self.assertRaisesRegex(ValueError, "Cited source hash differs"):
            audit(self.packet)

    def test_path_escape_and_forged_original(self):
        self.data["sources"]["city_limits"]["path"] = "../escape.json"
        self.save()
        with self.assertRaisesRegex(ValueError, "Unsafe cited source path"):
            audit(self.packet)
        self.data["sources"]["city_limits"]["path"] = "city_limits.json"
        self.data["source_kind"] = "original_review"
        self.save()
        with self.assertRaisesRegex(ValueError, "Original source required"):
            audit(self.packet, require_original=True)


if __name__ == "__main__":
    unittest.main()
