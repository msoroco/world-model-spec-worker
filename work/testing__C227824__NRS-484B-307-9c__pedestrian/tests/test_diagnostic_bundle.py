import json
import unittest
from runner import check_config


class ConstructionTest(unittest.TestCase):
    def test_contract(self):
        with open("config.json", encoding="utf-8") as stream:
            self.assertTrue(check_config(json.load(stream)))

    def test_original_source_gate(self):
        from pathlib import Path
        from reviewed_scene import plan
        case_id = json.load(open("config.json", encoding="utf-8"))["selected_case_id"]
        with self.assertRaises((ValueError, FileNotFoundError)):
            plan(Path("."), {"path": "absent.json", "sha256": "0" * 64}, case_id)
