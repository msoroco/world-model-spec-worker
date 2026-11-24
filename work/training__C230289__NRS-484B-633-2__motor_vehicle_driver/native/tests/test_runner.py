import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("runner", ROOT / "runner.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class BridgeDraftTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "config.json").read_text())

    def test_unselected_four_camera_plan(self):
        proof = runner.check(self.config)
        self.assertEqual(proof["frame_count"], 600)
        self.assertEqual(len(proof["views"]), 4)
        self.assertFalse(proof["selected"])

    def test_cell_change_rejected(self):
        self.config["frozen_cell"]["control"] = "none"
        with self.assertRaisesRegex(ValueError, "frozen cell changed"):
            runner.check(self.config)

    def test_legal_claim_rejected(self):
        self.config["legal_verdict"] = "violation"
        with self.assertRaisesRegex(ValueError, "unproved outcome claimed"):
            runner.check(self.config)

    def test_generic_road_survey_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "survey.json"
            path.write_text(json.dumps({"source_kind": "original_native_bridge_survey",
                                        "map_name": "Town", "highway_source_id": "road",
                                        "structure_source_id": "", "chapter_408_source_id": ""}))
            with self.assertRaisesRegex(ValueError, "highway bridge geometry provenance missing"):
                runner.read_survey(path)


if __name__ == "__main__":
    unittest.main()
