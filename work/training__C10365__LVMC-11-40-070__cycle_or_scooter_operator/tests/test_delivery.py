"""Independent CPU checks of exact selected C10365 delivery contracts."""
import json
import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
os.environ.setdefault("SCENARIO_PIPELINE_OUTPUT_ROOT", str(REPO / ".runtime-work/c10365-test-runtime"))
os.environ.setdefault("TMPDIR", str(REPO / ".runtime-work"))
sys.path[:0] = [str(REPO / "runtime"), str(REPO / "runtime/scenario_pipeline")]

from scenario_pipeline.worker_exchange.execution_manifest import validate as validate_execution
from scenario_pipeline.worker_exchange.semantic_delivery import validate as validate_semantic
from scenario_pipeline.worker_exchange.package_compatibility import check_receipts
from scenario_pipeline.worker_exchange.delivery_handoff import validate_case


class SelectedDelivery(unittest.TestCase):
    def test_current_runtime_and_source_bound_candidates(self):
        manifest = validate_execution(REPO, HERE.name)
        self.assertEqual(len(manifest["cases"]), 2)
        self.assertTrue(check_receipts(REPO, HERE, manifest))
        for case in manifest["cases"]:
            self.assertEqual(len(case["candidates"]), 2)
            self.assertEqual(validate_case(HERE, case, ["full-train"])["test_exit_code"], 0)

    def test_semantic_and_physical_proofs(self):
        assignment = json.loads((REPO / "inputs" / HERE.name / "assignment.json").read_text())
        manifest = json.loads((HERE / "execution-manifest.json").read_text())
        self.assertEqual(validate_semantic(HERE, assignment, manifest)["selected_cases"], 2)
        for suffix in ("a", "b"):
            proof = json.loads((HERE / "physical" / ("probe-" + suffix) / "preparation-proof.json").read_text())
            self.assertEqual({f["kind"] for f in proof["fixtures"]},
                             {"complete_motion", "incomplete_motion", "missing_evidence"})
            self.assertEqual(proof["lifecycle"]["events"][-2:],
                             ["owner_released", "saved_processing_started"])


if __name__ == "__main__":
    unittest.main()
