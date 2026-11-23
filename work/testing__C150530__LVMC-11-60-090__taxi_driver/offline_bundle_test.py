"""Exact materialized taxi construction checks run by pinned runtime.py offline."""
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from candidate_opendrive import inspect as inspect_xodr
from stand_route import inspect as inspect_route
from runner import check_materialized_bundle, check_static


class ExactBundleTest(unittest.TestCase):
    def test_case_identity_and_materialized_sources(self):
        config = json.loads((ROOT / "config.json").read_text())
        selected = config["selected_case_id"]
        case = selected.rsplit("__", 1)[-1]
        self.assertIn(case, ("near_stand", "far_stand"))
        check_materialized_bundle(ROOT, case)
        layout = json.loads((ROOT / "candidates" / (case + ".json")).read_text())
        inspect_route(layout)
        source = (ROOT / "candidates" / (case + ".xodr")).read_bytes()
        inspect_xodr(source, case)
        self.assertEqual(config["candidate_map_sha256"], hashlib.sha256(source).hexdigest())
        result = check_static(case)
        self.assertEqual(result["case_id"], selected)
        self.assertFalse(result["native_started"])

    def test_capture_contract_identifies_four_sources(self):
        config = json.loads((ROOT / "config.json").read_text())
        self.assertEqual(config["rate_hz"], 20)
        self.assertEqual(config["duration_s"], 35)
        self.assertEqual(config["cameras"], ["overview", "approach",
                                              "reference_corner", "driver_reference"])
        self.assertEqual(config["context_packet"], "reviewed-context.json")


if __name__ == "__main__":
    unittest.main()
