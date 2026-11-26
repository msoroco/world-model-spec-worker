"""Synthetic index fixtures test independent case and comparison coverage."""

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from delivery_audit import audit
from street_scene_construction import ASSIGNMENT


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        plan = json.loads((Path(__file__).resolve().parents[1] / "case-plan.json").read_text())
        cases = {}
        for case in plan["cases"]:
            directory = self.root / case["variant"]
            directory.mkdir()
            items = {}
            for key in ("context", "trace", "receipt", "camera_manifest", "measurement"):
                path = directory / (key + ".json")
                value = ({"physical_acceptance": "unverified"} if key == "measurement"
                         else {"synthetic_unit_fixture": key})
                path.write_text(json.dumps(value) + "\n")
                items[key] = {"path": str(path.relative_to(self.root)),
                              "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            cases[case["case_id"]] = items
        self.index = self.root / "index.json"
        self.value = {"assignment_id": ASSIGNMENT, "source_kind": "original_native_delivery",
                      "cases": cases}
        self.write()

    def write(self):
        self.index.write_text(json.dumps(self.value, sort_keys=True) + "\n")

    def test_all_cases_and_comparisons_invoked(self):
        with patch("delivery_audit.finalize", return_value={"physical_acceptance": "unverified"}) as finalize:
            with patch("delivery_audit.compare", return_value={"fixed_sources_and_protocol_checked": True}) as compare:
                result = audit(self.index)
        self.assertEqual((finalize.call_count, compare.call_count), (9, 8))
        self.assertEqual((result["case_count"], result["comparison_count"]), (9, 8))
        self.assertEqual(result["legal_judgment"], "unresolved")

    def test_missing_case_rejected(self):
        self.value["cases"].pop(next(iter(self.value["cases"])))
        self.write()
        with self.assertRaisesRegex(ValueError, "exact nine"):
            audit(self.index)

    def test_changed_source_bytes_rejected(self):
        first = next(iter(self.value["cases"].values()))["context"]
        (self.root / first["path"]).write_text("changed\n")
        with patch("delivery_audit.finalize", return_value={"physical_acceptance": "unverified"}):
            with self.assertRaisesRegex(ValueError, "source changed"):
                audit(self.index)


if __name__ == "__main__":
    unittest.main()
