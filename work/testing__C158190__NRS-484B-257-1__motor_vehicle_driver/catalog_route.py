"""Audit the frozen cell route for the assigned yield-sign branch."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ASSIGNMENT = "testing__C158190__NRS-484B-257-1__motor_vehicle_driver"
TARGET = "testing__C158208__NRS-484B-257-1__motor_vehicle_driver"
KEYS = ("layout", "maneuver")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(repo: Path) -> dict:
    origin_path = repo / "inputs" / ASSIGNMENT / "assignment.json"
    target_path = repo / "inputs" / TARGET / "assignment.json"
    catalog_path = repo / "inputs/coverage/candidate-cells.json"
    batch_path = repo / "batch.json"
    origin = json.loads(origin_path.read_text())
    target = json.loads(target_path.read_text())
    catalog = json.loads(catalog_path.read_text())
    batch = json.loads(batch_path.read_text())
    cells = {cell["cell_id"]: cell for cell in catalog["cells"]}
    source = cells[origin["cell_id"]]
    match = cells[target["cell_id"]]
    if origin["assignment_id"] != ASSIGNMENT or target["assignment_id"] != TARGET:
        raise ValueError("assignment identity changed")
    if origin["law_id"] != target["law_id"] or origin["actor"] != target["actor"]:
        raise ValueError("target law or actor differs")
    if any(source[k] != match[k] for k in KEYS):
        raise ValueError("target layout or maneuver differs")
    if source["control"] != "stop_sign" or match["control"] != "yield_sign":
        raise ValueError("expected fixed control conflict is absent")
    if origin["actor"] not in match["candidate_ego_parties"]:
        raise ValueError("target actor is ineligible")
    if ASSIGNMENT not in batch["assignments"] or TARGET not in batch["assignments"]:
        raise ValueError("target is not an existing batch assignment")
    if not {"demo-test", "full-test"}.issubset(set(match["allocated_sets"])):
        raise ValueError("target lacks testing role allocation")
    if {"demo-train", "full-train", "held-out"} & set(match["allocated_sets"]):
        raise ValueError("target conflicts with another role")
    exact_matches = [cell["cell_id"] for cell in catalog["cells"]
                     if cell["control"] == "yield_sign"
                     and all(cell[k] == source[k] for k in KEYS)
                     and origin["actor"] in cell["candidate_ego_parties"]]
    if exact_matches != [match["cell_id"]]:
        raise ValueError("exact compatible yield cell inventory changed")
    return {
        "format": "worker-cell-route-audit",
        "assignment_id": ASSIGNMENT,
        "assignment_sha256": sha(origin_path),
        "candidate_catalog_sha256": sha(catalog_path),
        "batch_sha256": sha(batch_path),
        "fixed_original_cell": {k: source[k] for k in ("cell_id", "layout", "maneuver", "control")},
        "existing_compatible_assignment_id": TARGET,
        "existing_compatible_assignment_sha256": sha(target_path),
        "existing_compatible_cell": {k: match[k] for k in ("cell_id", "layout", "maneuver", "control")},
        "exact_compatible_yield_cells": exact_matches,
        "binding_disposition": "Route the yield-governed branch to the already assigned C158208 package; do not create a duplicate supplemental binding or relabel C158190 as a yield-sign cell.",
        "original_assignment_disposition": "C158190 remains partial until its assigned branch has a valid source-bound allocation and its own strict gate passes.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.repo.resolve()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
