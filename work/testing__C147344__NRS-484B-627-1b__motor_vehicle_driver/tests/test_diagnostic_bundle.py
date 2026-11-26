import json
import unittest
from pathlib import Path
from runner import check_config


class ConstructionTest(unittest.TestCase):
    def test_contract(self):
        with open(Path(__file__).resolve().parents[1] / "config.json", encoding="utf-8") as stream:
            self.assertTrue(check_config(json.load(stream)))

    def test_source_gate(self):
        from reviewed_scene import plan
        from pathlib import Path
        with self.assertRaises((ValueError, FileNotFoundError)):
            plan(Path("."), {"path": "absent.json", "sha256": "0" * 64},
                 json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text(encoding="utf-8"))["selected_case_id"])
