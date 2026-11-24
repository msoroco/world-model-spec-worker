import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("runner", ROOT / "runner.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class AlleyDraftTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "config.json").read_text())

    def test_unselected_plan(self):
        proof = runner.check(self.config)
        self.assertEqual(proof["frame_count"], 600)
        self.assertEqual(len(proof["views"]), 4)
        self.assertFalse(proof["no_goods_verified"])

    def test_cell_change_rejected(self):
        self.config["frozen_cell"]["layout"] = "road"
        with self.assertRaisesRegex(ValueError, "frozen cell changed"):
            runner.check(self.config)

    def test_legal_claim_rejected(self):
        self.config["legal_verdict"] = "violation"
        with self.assertRaisesRegex(ValueError, "unproved outcome claimed"):
            runner.check(self.config)

    def test_ordinance_source_required(self):
        survey = {"source_kind": "original_native_alley_survey",
                  "fixed_cell": self.config["frozen_cell"], "map_name": "Town",
                  "alley_boundary_source_id": "alley", "entrance_source_id": "entrance",
                  "highway_public_use_source_id": "public",
                  "city_block_source_id": "block", "rear_property_service_source_id": "rear",
                  "not_cul_de_sac_source_id": "through",
                  "frontage_600ft_source_id": "frontage-600",
                  "frontage_300ft_source_id": "frontage-300",
                  "building_uses_source_id": "uses",
                  "local_authority_source_id": "", "ordinance_status_source_id": ""}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "survey.json"
            path.write_text(json.dumps(survey))
            with self.assertRaisesRegex(ValueError, "local ordinance context missing"):
                runner.read_survey(path)


if __name__ == "__main__":
    unittest.main()
