"""Exported Section 11.52.070 is a conditional angle-parking exception."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from chapter_exception_inventory import inventory


class ChapterExceptionInventoryTests(unittest.TestCase):
    def test_source_and_site_conditions_are_retained(self):
        result = inventory(ROOT.parents[1] / "inputs/coverage/branch-sources.json")
        self.assertEqual(result["potential_exception"]["law_id"], "LVMC-11-52-070")
        self.assertEqual(len(result["potential_exception"]["site_conditions_to_acquire"]), 3)
        self.assertEqual(result["site_exception_status"], "unresolved")
        self.assertIn("not complete Chapter review", result["review_scope"])

    def test_changed_exception_wording_rejected(self):
        source = ROOT.parents[1] / "inputs/coverage/branch-sources.json"
        data = json.loads(source.read_text())
        data["laws"]["LVMC-11-52-070"]["law"]["text"] = "Angle parking permitted everywhere"
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "changed.json"
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "wording differs"):
                inventory(path)


if __name__ == "__main__":
    unittest.main()
