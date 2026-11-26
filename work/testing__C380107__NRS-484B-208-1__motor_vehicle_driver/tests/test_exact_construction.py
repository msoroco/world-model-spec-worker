import json
import unittest
from pathlib import Path
from runner import check_config
from reviewed_site import plan

class ExactConstruction(unittest.TestCase):
    def test_exact_config(self):
        self.assertTrue(check_config(json.loads(Path("config.json").read_text())))

    def test_original_authority_gate(self):
        case_id=json.loads(Path("config.json").read_text())["selected_case_id"]
        with self.assertRaises(ValueError):
            plan(Path("."), {"path":"absent.json","sha256":"0"*64}, case_id)
