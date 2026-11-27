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
    assert all(not cell.get("candidate_ego_parties") for cell in cells)
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
        "affirmatively_listed_actor_eligible_roadway_entry_count": len(eligible),
        "catalog_actor_lists_all_empty": True,
        "unused_private_way_entry_candidate": "C195651",
        "current_runtime_supplemental_binding_eligible": False,
        "result": "The frozen exit_road case does not establish the separate roadway-entry duty. The catalog lists three enter_road cells but gives no affirmative actor eligibility for any of its 1243 rows. The pinned branch_coverage.assignments gate explicitly requires actor membership, so a current-runtime supplemental binding would fail as ineligible, regardless of whether an empty list semantically represents conflict or omitted metadata.",
        "required_resolution": "A permitted frozen catalog/runtime refresh that affirms motor_vehicle_driver eligibility for an enter_road cell, or a separately source-bound same-cell exit-then-return construction preserving the fixed exit_road witness. Current two-case construction is insufficient.",
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"catalog_count": len(cells), "entry_count": len(entrant), "affirmatively_listed_eligible_count": len(eligible), "receipt_sha256": sha(REPORT)}))


if __name__ == "__main__":
    main()
