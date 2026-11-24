"""Pinned semantic-stage validation and source rejection for all five cases."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(REPO / ".runtime-work" / "c10307-semantic-tests")
sys.path.insert(0, str(REPO / "runtime" / "scenario_pipeline"))
from worker_exchange.semantic_delivery import validate


class SemanticStageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assignment = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
        cls.manifest = json.loads((ROOT / "execution-manifest.json").read_text())

    def test_all_five_exact_cases_validate(self):
        receipt = validate(ROOT, self.assignment, self.manifest)
        self.assertEqual(receipt["selected_cases"], 5)
        self.assertEqual(receipt["stage_count"], 6)

    def test_missing_source_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            shutil.copytree(ROOT / "proposals", folder / "proposals")
            shutil.copy(ROOT / "construction.json", folder / "construction.json")
            (folder / "cases").mkdir()
            for entry in self.manifest["cases"][1:]:
                target = folder / entry["construction"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(ROOT / entry["construction"], target)
            (folder / "proposals" / "judgment-1.json").unlink()
            with self.assertRaisesRegex(Exception, "judgment-1|source|No such file"):
                validate(folder, self.assignment, self.manifest)


if __name__ == "__main__":
    unittest.main()
