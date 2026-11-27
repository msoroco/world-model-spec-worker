"""Audit frozen source eligibility for a separate highway-entry binding."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUTPUT = HERE / "entry-registry-proof.json"
CURRENT = "training__C227853__NRS-484B-410__motor_vehicle_driver"
EXISTING = "training__C177626__NRS-484B-260__motor_vehicle_driver"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def eligible(cell, role="training"):
    forbidden = {"full-test", "demo-test", "held-out"} if role == "training" else {"full-train", "demo-train", "held-out"}
    return "motor_vehicle_driver" in cell.get("candidate_ego_parties", []) and not forbidden.intersection(cell.get("allocated_sets", []))


def audit():
    source = ROOT / "inputs/coverage/candidate-cells.json"
    original_path = ROOT / "inputs" / CURRENT / "assignment.json"
    existing_path = ROOT / "inputs" / EXISTING / "assignment.json"
    catalog = json.loads(source.read_text())
    original = json.loads(original_path.read_text())
    existing = json.loads(existing_path.read_text())
    assert original["law_id"] == "NRS-484B-410"
    assert original["cell"]["maneuver"] == "depart_parked"
    assert existing["cell"]["maneuver"] == "enter_road"
    assert existing["cell"]["candidate_ego_parties"].count("motor_vehicle_driver") == 1
    cells = catalog["cells"]
    actor_cells = [c for c in cells if "motor_vehicle_driver" in c.get("candidate_ego_parties", [])]
    eligible_actor_cells = [c for c in actor_cells if eligible(c)]
    entry = [c for c in cells if c.get("maneuver") == "enter_road"]
    eligible_entry = [c["cell_id"] for c in entry if eligible(c)]
    assert len({c["cell_id"] for c in cells}) == len(cells)
    assert "C177626" not in {c["cell_id"] for c in cells}
    assert not actor_cells
    assert not eligible_actor_cells
    assert not eligible_entry
    mutation = dict(existing["cell"], allocated_sets=[])
    assert eligible(mutation)
    assert not eligible(dict(mutation, candidate_ego_parties=[]))
    assert not eligible(dict(mutation, allocated_sets=["full-test"]))
    result = {
        "format": "nrs-484b-410-entry-registry-audit-v1",
        "original_assignment": str(original_path.relative_to(ROOT)),
        "original_assignment_sha256": digest(original_path),
        "existing_entry_assignment": str(existing_path.relative_to(ROOT)),
        "existing_entry_assignment_sha256": digest(existing_path),
        "candidate_catalog": str(source.relative_to(ROOT)),
        "candidate_catalog_sha256": digest(source),
        "auditor_sha256": digest(Path(__file__)),
        "catalog_cells": len(cells),
        "motor_vehicle_driver_cells": len(actor_cells),
        "training_eligible_motor_vehicle_driver_cells": len(eligible_actor_cells),
        "entry_cells": [{"cell_id": c["cell_id"], "layout": c["layout"],
                         "control": c["control"], "actor_eligible": eligible(c)} for c in entry],
        "eligible_entry_cell_ids": eligible_entry,
        "existing_entry_cell_in_registry": False,
        "negative_mutations_rejected": ["actor_removed", "training_forbidden_set"],
        "hypothetical_added_existing_cell_eligible": True,
        "source_authorized_binding": False,
        "original_native_observed": False,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    result = audit()
    print(json.dumps({"catalog_cells": result["catalog_cells"],
                      "entry_cells": len(result["entry_cells"]),
                      "eligible_entry_cells": len(result["eligible_entry_cell_ids"])}))
