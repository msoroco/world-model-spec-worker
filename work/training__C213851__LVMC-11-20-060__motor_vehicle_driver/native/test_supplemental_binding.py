"""Exercise the pinned supplemental-binding gate on an isolated catalog copy."""

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path


ASSIGNMENT = "training__C213851__LVMC-11-20-060__motor_vehicle_driver"
SUPPLEMENT = "training__C195651__LVMC-11-20-060__motor_vehicle_driver"
ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "work" / ASSIGNMENT / "native/supplemental-binding-gate.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    output_root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if not output_root.is_relative_to((ROOT / ".runtime-work").resolve()):
        raise ValueError("Runtime output root must remain under .runtime-work")
    sys.path.insert(0, str(ROOT / "runtime"))
    from scenario_pipeline.worker_exchange.branch_coverage import assignments

    catalog_path = ROOT / "inputs/coverage/candidate-cells.json"
    original_path = ROOT / "inputs" / ASSIGNMENT / "assignment.json"
    catalog = json.loads(catalog_path.read_text())
    original = json.loads(original_path.read_text())
    candidate = next(c for c in catalog["cells"] if c["cell_id"] == "C195651")
    if candidate["candidate_ego_parties"] or candidate["allocated_sets"]:
        raise ValueError("Catalog eligibility changed; redo the allocation review")
    supplemental = dict(original, assignment_id=SUPPLEMENT, cell_id="C195651",
                        cell=candidate)
    scratch = ROOT / ".runtime-work"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="c213851-binding-", dir=scratch) as tmp:
        repo = Path(tmp)
        (repo / "inputs/coverage").mkdir(parents=True)
        (repo / "inputs" / ASSIGNMENT).mkdir()
        (repo / "work/_shared").mkdir(parents=True)
        (repo / "work" / SUPPLEMENT).mkdir()
        shutil.copy2(catalog_path, repo / "inputs/coverage/candidate-cells.json")
        shutil.copy2(original_path, repo / "inputs" / ASSIGNMENT / "assignment.json")
        (repo / "work" / SUPPLEMENT / "assignment.json").write_text(
            json.dumps(supplemental, indent=2) + "\n")
        matrix = {"additional_bindings": [{
            "assignment_id": SUPPLEMENT,
            "original_assignment_id": ASSIGNMENT,
            "original_cell_incompatibility": "C213851 fixes exit_road",
            "binding_reason": "Test the roadway-entry candidate against the pinned gate",
        }]}
        (repo / "work/_shared/branch-coverage.json").write_text(
            json.dumps(matrix, indent=2) + "\n")
        try:
            assignments(repo, {"assignments": {ASSIGNMENT: {"input_sha256": sha(original_path)}},
                               "full_branch_coverage_required": True})
        except ValueError as error:
            if str(error) != "Ineligible supplemental binding":
                raise
            outcome = str(error)
        else:
            raise AssertionError("Actor-ineligible supplemental binding was accepted")
    receipt = {
        "format": "worker-supplemental-binding-gate-proof",
        "assignment_id": ASSIGNMENT,
        "proposed_assignment_id": SUPPLEMENT,
        "frozen_catalog_sha256": sha(catalog_path),
        "frozen_assignment_sha256": sha(original_path),
        "runtime_gate_sha256": sha(ROOT / "runtime/scenario_pipeline/worker_exchange/branch_coverage.py"),
        "candidate_ego_parties": candidate["candidate_ego_parties"],
        "tested_command": "branch_coverage.assignments on an isolated copy of the frozen catalog and proposed binding",
        "observed_rejection": outcome,
        "runtime_gate_passed": False,
        "physical_or_legal_outcome_claimed": False,
    }
    OUTPUT.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"expected_rejection": outcome, "receipt_sha256": sha(OUTPUT)}))


if __name__ == "__main__":
    main()
