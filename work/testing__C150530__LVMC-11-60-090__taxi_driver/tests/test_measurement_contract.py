import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build_measurement_contract import build


class MeasurementContractTest(unittest.TestCase):
    def test_both_cases_and_all_selected_requirements_are_source_bound(self):
        contract = build()
        self.assertEqual(len(contract["cases"]), 2)
        self.assertEqual([item["disposition_index"] for item in contract["selected_requirements"]],
                         [0, 1, 2])
        self.assertEqual({item["case_id"].rsplit("__", 1)[-1] for item in contract["cases"]},
                         {"near_stand", "far_stand"})
        for case in contract["cases"]:
            self.assertEqual(hashlib.sha256((ROOT / case["candidate_map"]).read_bytes()).hexdigest(),
                             case["candidate_map_sha256"])
        for code in contract["code"].values():
            self.assertEqual(hashlib.sha256((ROOT / code["path"]).read_bytes()).hexdigest(),
                             code["sha256"])

    def test_materialized_contract_matches_builder(self):
        self.assertEqual(json.loads((ROOT / "measurement-contract.json").read_text()), build())


if __name__ == "__main__":
    unittest.main()
