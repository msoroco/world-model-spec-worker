"""Source review of the subsection 3 dependency and selected-case diagnostics."""
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(__file__).resolve().parent
AID = FOLDER.name
EXCEPTIONS = {
    "a": "When entering or exiting an alley or driveway",
    "b": "When operating or parking a disabled vehicle",
    "c": "To avoid conflict with other traffic",
    "d": "In the performance of official duties",
    "e": "In compliance with the directions of a police officer",
    "f": "In an emergency",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def review():
    assignment_path = ROOT / "inputs" / AID / "assignment.json"
    coverage_path = ROOT / "inputs/coverage/branch-sources.json"
    plan_path = FOLDER / "case-plan.json"
    assignment = json.loads(assignment_path.read_text())
    coverage = json.loads(coverage_path.read_text())
    plan = json.loads(plan_path.read_text())
    law4 = assignment["law"] if "law" in assignment else None
    if law4 is None:
        law4 = next((x for x in assignment.values() if isinstance(x, dict) and x.get("id") == "NRS-484B-270-4" and "text" in x), None)
    if law4 is None:
        law4 = plan["source_law"]
    law4_text = law4["text"]
    law3_text = coverage["laws"]["NRS-484B-270-3"]["law"]["text"] if "laws" in coverage else coverage["NRS-484B-270-3"]["law"]["text"]
    if "Except as otherwise provided in subsection 3" not in law4_text:
        raise ValueError("Subsection 4 cross-reference missing from original source")
    if any(clause not in law3_text for clause in EXCEPTIONS.values()):
        raise ValueError("A subsection 3 exception clause differs from original source")
    if "shall yield the right-of-way" not in law3_text:
        raise ValueError("Subsection 3 yield dependency missing")
    pair = json.loads((FOLDER / "current-v2-pair-audit.json").read_text())
    if len(pair["cases"]) != 2 or pair["cases"][0]["intersection_cycle_overlap_frames"] != 0:
        raise ValueError("Retained unselected crossing diagnostic changed")
    sys.path.insert(0, str(FOLDER / "native"))
    from route_v2 import check as route_check
    route = route_check()
    return {
        "format": "c111250-subsection3-source-review-v1",
        "assignment_id": AID,
        "source_sha256": {"assignment": sha(assignment_path), "branch_sources": sha(coverage_path),
                          "case_plan": sha(plan_path), "unselected_pair_audit": sha(FOLDER / "current-v2-pair-audit.json")},
        "cross_reference": "NRS 484B.270(4) except as otherwise provided in NRS 484B.270(3)",
        "subsection3_exception_clauses": EXCEPTIONS,
        "subsection3_yield_rule_retained": True,
        "current_diagnostic_limitation": "controlled_1 shows zero intersection-facility body overlap, so it does not construct the planned crossing; its compatibility and saved-processing receipts remain valid only as unselected diagnostics",
        "authored_route_review": route,
        "required_original_context": ["official facility designation and Native map readback",
                                      "original source identifying the subsection 3 circumstance and its timing",
                                      "original bicyclist, electric-bicyclist, scooter rider or pedestrian presence and yield observations",
                                      "saved Native body corners and full camera frame joins"],
        "legal_exception_proven": False,
        "physical_success_proven": False,
        "selected_delivery_proven": False,
    }


if __name__ == "__main__":
    proof = review()
    target = FOLDER / "subsection3-source-review.json"
    target.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": True, "output": target.name, "sha256": sha(target)}))
