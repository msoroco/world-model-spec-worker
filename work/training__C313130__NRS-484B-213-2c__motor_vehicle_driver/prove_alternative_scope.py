"""Reproduce candidate binding rejection without changing frozen or returned inputs."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[2]
AID = "training__C313130__NRS-484B-213-2c__motor_vehicle_driver"
SCRATCH = ROOT / ".runtime-work" / "c313130-alternative-scope"
sys.path.insert(0, str(ROOT / "runtime"))
from scenario_pipeline.worker_exchange import branch_coverage  # noqa: E402


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def trial(cell_id):
    trial_root = SCRATCH / cell_id
    candidate_id = f"training__{cell_id}__NRS-484B-213-2c__motor_vehicle_driver"
    (trial_root / "inputs" / AID).mkdir(parents=True, exist_ok=True)
    (trial_root / "inputs" / "coverage").mkdir(parents=True, exist_ok=True)
    (trial_root / "work" / "_shared").mkdir(parents=True, exist_ok=True)
    (trial_root / "work" / candidate_id).mkdir(parents=True, exist_ok=True)
    source = ROOT / "inputs" / AID / "assignment.json"
    shutil.copyfile(source, trial_root / "inputs" / AID / "assignment.json")
    inventory = ROOT / "inputs" / "coverage" / "candidate-cells.json"
    shutil.copyfile(inventory, trial_root / "inputs" / "coverage" / "candidate-cells.json")
    assignment = json.loads(source.read_text())
    assignment["assignment_id"] = candidate_id
    assignment["cell_id"] = cell_id
    (trial_root / "work" / candidate_id / "assignment.json").write_text(json.dumps(assignment) + "\n")
    matrix = {"additional_bindings": [{"assignment_id": candidate_id,
        "original_assignment_id": AID,
        "original_cell_incompatibility": "Original cell is a tunnel",
        "binding_reason": "Trial of alternative physical structure"}]}
    (trial_root / "work" / "_shared" / "branch-coverage.json").write_text(json.dumps(matrix) + "\n")
    batch = copy.deepcopy(json.loads((ROOT / "batch.json").read_text()))
    batch["full_branch_coverage_required"] = True
    try:
        branch_coverage.assignments(trial_root, batch)
    except ValueError as error:
        if str(error) != "Ineligible supplemental binding":
            raise
        cells = json.loads(inventory.read_text())["cells"]
        cell = next(c for c in cells if c["cell_id"] == cell_id)
        return {"cell_id": cell_id, "candidate_assignment_id": candidate_id,
            "validator": "scenario_pipeline.worker_exchange.branch_coverage.assignments",
            "rejection": str(error), "candidate_ego_parties": cell["candidate_ego_parties"],
            "allocated_sets": cell["allocated_sets"]}
    raise AssertionError("Unexpected accepted supplemental binding: " + candidate_id)


if __name__ == "__main__":
    output = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    assert ROOT / ".runtime-work" in output.parents
    SCRATCH.mkdir(parents=True, exist_ok=True)
    results = [trial(cell) for cell in ("C31940", "C349180")]
    print(json.dumps({"assignment_id": AID,
        "frozen_assignment_sha256": digest(ROOT / "inputs" / AID / "assignment.json"),
        "frozen_witness_sha256": digest(ROOT / "inputs" / AID / "witnesses.json"),
        "candidate_inventory_sha256": digest(ROOT / "inputs" / "coverage" / "candidate-cells.json"),
        "branch_sources_sha256": digest(ROOT / "inputs" / "coverage" / "branch-sources.json"),
        "trials": results}, indent=2))
