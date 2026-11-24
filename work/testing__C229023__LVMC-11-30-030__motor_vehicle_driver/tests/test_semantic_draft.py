import json
import os
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
output = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
if not output or not Path(output).resolve().is_relative_to((HERE.parents[1] / ".runtime-work").resolve()):
    raise ValueError("export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before semantic tests")
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "runtime"))
sys.path.insert(0, str(HERE.parents[1] / "runtime" / "scenario_pipeline"))
from scenario_pipeline.worker_exchange import semantic_delivery
from build_semantic_draft import JUDGMENTS, recording_description


class SemanticDraftTests(unittest.TestCase):
    def test_exact_source_law_and_all_selected_cases_validate(self):
        assignment = json.loads((HERE.parents[1] / "inputs" / HERE.name / "assignment.json").read_text())
        manifest = json.loads((HERE / "execution-manifest.draft.json").read_text())
        result = semantic_delivery.validate(HERE, assignment, manifest)
        self.assertEqual(result["stage_count"], 9)
        self.assertEqual(result["selected_cases"], 6)
        self.assertEqual(len(JUDGMENTS), 4)
        self.assertIn("complete_native_source_and_pixels",
                      {channel["name"] for channel in recording_description()["channels"]})


if __name__ == "__main__":
    unittest.main()
