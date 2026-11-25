"""Check the frozen catalog for an actor-eligible opposite-turn cell."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ASSIGNMENT = "training__C111071__NRS-484B-307-9b__motorcycle_or_moped_operator"


def load(relative):
    path = ROOT / relative
    data = path.read_bytes()
    return json.loads(data), hashlib.sha256(data).hexdigest()


def main():
    source, source_hash = load(f"inputs/{ASSIGNMENT}/assignment.json")
    catalog, catalog_hash = load("inputs/coverage/candidate-cells.json")
    batch, batch_hash = load("batch.json")
    validator_path = ROOT / "runtime/scenario_pipeline/worker_exchange/branch_coverage.py"
    validator_bytes = validator_path.read_bytes()
    assert b"a['actor'] not in cell['candidate_ego_parties']" in validator_bytes
    validator_hash = hashlib.sha256(validator_bytes).hexdigest()
    assert source["cell"]["maneuver"] == "straight"
    assert "turn in the direction opposite" in source["law"]["text"]
    actor = source["actor"]
    turn_cells = [
        cell for cell in catalog["cells"]
        if cell["layout"] == "intersection"
        and cell["control"] == "inoperative_signal"
        and cell["maneuver"] in ("left_turn", "right_turn")
    ]
    eligible = [cell["cell_id"] for cell in turn_cells if actor in cell["candidate_ego_parties"]]
    existing = []
    for aid in batch["assignments"]:
        assignment, _ = load(f"inputs/{aid}/assignment.json")
        if (assignment["actor"] == actor and assignment["law_id"] == source["law_id"]
                and assignment["cell"]["maneuver"] in ("left_turn", "right_turn")):
            existing.append(aid)
    report = {
        "format": "c111071-opposite-turn-eligibility-proof-v1",
        "assignment_id": ASSIGNMENT,
        "source_sha256": source_hash,
        "catalog_sha256": catalog_hash,
        "batch_sha256": batch_hash,
        "branch_validator_sha256": validator_hash,
        "branch_validator_rule": "a['actor'] not in cell['candidate_ego_parties']",
        "turn_cells": [
            {key: cell[key] for key in ("cell_id", "maneuver", "control", "candidate_ego_parties", "allocated_sets")}
            for cell in turn_cells
        ],
        "actor_eligible_cell_ids": eligible,
        "existing_same_law_turn_assignments": existing,
        "blocked_prerequisite": "Source-authorized actor-eligible opposite-turn binding or accepted source-hashed evidence reuse",
    }
    assert not eligible and not existing, "An opposite-turn route is available; review the binding"
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
