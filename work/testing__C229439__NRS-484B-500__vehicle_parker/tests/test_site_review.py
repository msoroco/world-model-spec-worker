import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from parking_place import ASSIGNMENT
from site_review import SOURCE_KINDS, reviewed_site


class SiteReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case_id = ASSIGNMENT + "__park_inside_hazard"
        self.site = {"assignment_id": ASSIGNMENT, "case_id": self.case_id,
                     "review_status": "reviewed_original_source", "map_id": "map-a",
                     "device_id": "device-a", "designated_place_id": "place-a",
                     "device_instructions": "no parking", "device_erected": True,
                     "place_context_for_review": "hazardous",
                     "designated_place_polygon": [[0, 0], [10, 0], [10, 5], [0, 5]],
                     "sources": {}}
        for kind in SOURCE_KINDS:
            record = {"source_kind": kind, "map_id": "map-a", "device_id": "device-a",
                      "designated_place_id": "place-a", "erected": True,
                      "instructions": "no parking", "polygon": self.site["designated_place_polygon"],
                      "context_for_review": "hazardous"}
            path = self.root / (kind + ".json")
            data = json.dumps(record).encode()
            path.write_bytes(data)
            self.site["sources"][kind] = {"origin": "reviewed_original", "path": path.name,
                                           "sha256": hashlib.sha256(data).hexdigest()}
        self.site_path = self.root / "site.json"
        self.write_site()

    def write_site(self):
        self.site_path.write_text(json.dumps(self.site), encoding="utf-8")

    def test_source_bindings(self):
        receipt = reviewed_site(self.site_path, self.case_id)
        self.assertEqual(set(receipt["source_bindings"]), set(SOURCE_KINDS))

    def test_missing_review_rejected(self):
        self.site["review_status"] = "draft"
        self.write_site()
        with self.assertRaisesRegex(ValueError, "review"):
            reviewed_site(self.site_path, self.case_id)

    def test_stale_device_source_rejected(self):
        (self.root / "device.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash differs"):
            reviewed_site(self.site_path, self.case_id)

    def test_extent_identity_rejected(self):
        path = self.root / "extent.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record["polygon"] = [[0, 0], [9, 0], [9, 5], [0, 5]]
        data = json.dumps(record).encode()
        path.write_bytes(data)
        self.site["sources"]["extent"]["sha256"] = hashlib.sha256(data).hexdigest()
        self.write_site()
        with self.assertRaisesRegex(ValueError, "extent differs"):
            reviewed_site(self.site_path, self.case_id)

    def test_escape_rejected(self):
        self.site["sources"]["map"]["path"] = "../escape.json"
        self.write_site()
        with self.assertRaisesRegex(ValueError, "escapes"):
            reviewed_site(self.site_path, self.case_id)

    def test_symlink_source_rejected(self):
        (self.root / "map-link.json").symlink_to(self.root / "map.json")
        self.site["sources"]["map"]["path"] = "map-link.json"
        self.write_site()
        with self.assertRaisesRegex(ValueError, "escapes"):
            reviewed_site(self.site_path, self.case_id)


if __name__ == "__main__":
    unittest.main()
