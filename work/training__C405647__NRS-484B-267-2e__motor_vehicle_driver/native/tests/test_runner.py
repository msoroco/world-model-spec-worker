import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("runner", ROOT / "runner.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class EmergencyDraftTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "config.json").read_text())

    def test_unselected_plan(self):
        proof = runner.check(self.config)
        self.assertEqual(proof["frame_count"], 600)
        self.assertEqual(len(proof["views"]), 4)
        self.assertFalse(proof["feasibility_verified"])

    def test_cell_change_rejected(self):
        self.config["frozen_cell"]["control"] = "none"
        with self.assertRaisesRegex(ValueError, "frozen cell changed"):
            runner.check(self.config)

    def test_legal_claim_rejected(self):
        self.config["legal_verdict"] = "violation"
        with self.assertRaisesRegex(ValueError, "unproved outcome claimed"):
            runner.check(self.config)

    def test_lane_survey_required(self):
        survey = {"source_kind": "original_native_emergency_lane_survey",
                  "fixed_cell": self.config["frozen_cell"], "map_name": "Town",
                  "lane_topology_source_id": "", "emergency_authorization_source_id": ""}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "survey.json"
            path.write_text(json.dumps(survey))
            with self.assertRaisesRegex(ValueError, "emergency, lane or exception sources missing"):
                runner.read_survey(path)


if __name__ == "__main__":
    unittest.main()
