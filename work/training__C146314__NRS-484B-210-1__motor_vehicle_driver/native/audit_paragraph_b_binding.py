"""Check whether the frozen catalog permits an NRS 484B.210(1)(b) cell binding."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ASSIGNMENT_ID = "training__C146314__NRS-484B-210-1__motor_vehicle_driver"
ASSIGNMENT_PATH = ROOT / "inputs" / ASSIGNMENT_ID / "assignment.json"
CATALOG_PATH = ROOT / "inputs/coverage/candidate-cells.json"
RECEIPT_PATH = Path(__file__).with_name("paragraph-b-catalog-review.json")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def review(assignment, catalog):
    law = assignment["law"]["text"]
    required = "two or more lines of moving vehicles in each direction"
    if required not in law:
        raise ValueError("Frozen paragraph (b) two-direction source is missing")
    if assignment["cell"]["layout"] != "one_way_multilane":
        raise ValueError("Frozen C146314 layout changed")
    if assignment["cell"]["maneuver"] != "overtake_right":
        raise ValueError("Frozen C146314 maneuver changed")
    if assignment["actor"] != "motor_vehicle_driver":
        raise ValueError("Frozen C146314 actor changed")
    if catalog["format"] != "worker-candidate-cells-v1":
        raise ValueError("Wrong candidate catalog format")
    cells = catalog["cells"]
    if len({cell["cell_id"] for cell in cells}) != len(cells):
        raise ValueError("Duplicate candidate cell")
    matching = [cell for cell in cells if cell["maneuver"] == "overtake_right"
                and cell["control"] == "other_vehicle"]
    if not matching:
        raise ValueError("No right-pass/other-vehicle candidates")
    divided = next((cell for cell in matching if cell["cell_id"] == "C81424"), None)
    if divided is None or divided["layout"] != "divided_road":
        raise ValueError("Divided-road candidate absent or changed")
    role = assignment["role"]
    forbidden = ({"full-test", "demo-test", "held-out"} if role == "training"
                 else {"full-train", "demo-train", "held-out"})
    eligible = [cell for cell in matching
                if assignment["actor"] in cell["candidate_ego_parties"]
                and not forbidden.intersection(cell["allocated_sets"])]
    return {
        "candidate_count": len(cells),
        "right_pass_other_vehicle_count": len(matching),
        "actor_eligible_right_pass_count": len(eligible),
        "divided_road_candidate": {
            "cell_id": divided["cell_id"],
            "layout": divided["layout"],
            "candidate_ego_parties": divided["candidate_ego_parties"],
            "allocated_sets": divided["allocated_sets"],
            "actor_eligible": divided in eligible,
            "four_lane_geometry_proven_by_catalog": False,
        },
        "selected_binding": None,
        "requires": "Source-authorized actor eligibility and a distinct supplemental assignment before paragraph (b) selection",
    }


def main():
    assignment = json.loads(ASSIGNMENT_PATH.read_text())
    catalog = json.loads(CATALOG_PATH.read_text())
    result = review(assignment, catalog)
    assert result["actor_eligible_right_pass_count"] == 0
    assert result["divided_road_candidate"]["actor_eligible"] is False
    changed = json.loads(json.dumps(catalog))
    next(cell for cell in changed["cells"] if cell["cell_id"] == "C81424")["candidate_ego_parties"] = ["motor_vehicle_driver"]
    assert review(assignment, changed)["actor_eligible_right_pass_count"] == 1
    changed_assignment = json.loads(json.dumps(assignment))
    changed_assignment["cell"]["layout"] = "divided_road"
    try:
        review(changed_assignment, catalog)
    except ValueError as error:
        assert str(error) == "Frozen C146314 layout changed"
    else:
        raise AssertionError("Changed frozen cell was accepted")
    receipt = {
        "format": "c146314-paragraph-b-catalog-review-v1",
        "assignment_id": ASSIGNMENT_ID,
        "source_assignment": str(ASSIGNMENT_PATH.relative_to(ROOT)),
        "source_assignment_sha256": digest(ASSIGNMENT_PATH),
        "source_catalog": str(CATALOG_PATH.relative_to(ROOT)),
        "source_catalog_sha256": digest(CATALOG_PATH),
        "auditor": str(Path(__file__).relative_to(ROOT)),
        "auditor_sha256": digest(Path(__file__)),
        "positive_source_check": "passed",
        "changed_layout_negative": "rejected",
        "actor_eligibility_mutation": "becomes eligible only after changing frozen catalog",
        **result,
    }
    RECEIPT_PATH.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"candidate_count": result["candidate_count"],
                      "matching_count": result["right_pass_other_vehicle_count"],
                      "actor_eligible_count": result["actor_eligible_right_pass_count"]}))


if __name__ == "__main__":
    main()
