"""Check whether the frozen catalog authorizes a roadway-entry allocation."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
AID = "training__C213851__LVMC-11-20-060__motor_vehicle_driver"
CATALOG = ROOT / "inputs/coverage/candidate-cells.json"
ASSIGNMENT = ROOT / "inputs" / AID / "assignment.json"
REPORT = ROOT / "work" / AID / "native/roadway-entry-scope-gap.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    catalog = json.loads(CATALOG.read_text())
    assignment = json.loads(ASSIGNMENT.read_text())
    cells = catalog["cells"]
    actor = assignment["actor"]
    entrant = [cell for cell in cells if cell["maneuver"] == "enter_road"]
    eligible = [cell for cell in entrant if actor in cell.get("candidate_ego_parties", [])]
    assert assignment["cell"]["maneuver"] == "exit_road"
    assert entrant and not eligible
    report = {
        "format": "worker-roadway-entry-scope-gap",
        "assignment_id": AID,
        "assignment_sha256": sha(ASSIGNMENT),
        "catalog_source": "inputs/coverage/candidate-cells.json",
        "catalog_sha256": sha(CATALOG),
        "actor": actor,
        "frozen_maneuver": assignment["cell"]["maneuver"],
        "catalog_count": len(cells),
        "roadway_entry_cells": [
            {
                "cell_id": cell["cell_id"],
                "layout": cell["layout"],
                "control": cell["control"],
                "candidate_ego_parties": cell.get("candidate_ego_parties", []),
                "allocated_sets": cell.get("allocated_sets", []),
            }
            for cell in entrant
        ],
        "actor_eligible_roadway_entry_count": len(eligible),
        "result": "No authorized actor-eligible roadway-entry catalog cell; the frozen exit_road cell cannot establish the separate upon-entering-roadway duty.",
        "required_resolution": "Supply a reviewed motor_vehicle_driver roadway-entry cell allocation or a source-backed same-cell construction that preserves the fixed exit_road witness without relabeling it.",
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"catalog_count": len(cells), "entry_count": len(entrant), "eligible_count": len(eligible), "receipt_sha256": sha(REPORT)}))


if __name__ == "__main__":
    main()
