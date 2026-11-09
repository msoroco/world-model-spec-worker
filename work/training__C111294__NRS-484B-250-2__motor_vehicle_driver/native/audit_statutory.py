"""Exact-source statutory coverage crosswalk; does not infer legal outcomes."""
import json
from pathlib import Path

from build import CASE, PLAN, SOURCE, SOURCE_SHA, sha, put

HERE = Path(__file__).resolve().parent
REQUIRED = {
    "different_highways": "from different highways",
    "approximate_entry": "at approximately the same time",
    "left_yields_right": "driver of the vehicle on the left shall yield the right-of-way to the vehicle on the right",
    "subsection4_dependency": "Except as otherwise provided in subsection 4",
    "official_control_exception": "does not apply at intersections controlled by official traffic-control devices",
    "opposite_left_turn_exception": "or to vehicles approaching each other from opposite directions, when the driver of one of the vehicles is intending to or is making a left turn",
}


def audit():
    source = json.loads(SOURCE.read_text())
    plan = json.loads(PLAN.read_text())
    law = source["law_record"]["text"]
    if sha(SOURCE) != SOURCE_SHA or plan["source_law"]["text"] != law:
        raise ValueError("Frozen law or plan source changed")
    if any(fragment not in law for fragment in REQUIRED.values()):
        raise ValueError("Exact statutory clause missing")
    cases = plan["cases"]
    if len(cases) != 2 or any(c["kind"] != "unselected_native_request" for c in cases):
        raise ValueError("Controlled case disposition changed")
    if any(c["case_id"] != CASE.name + "__controlled_" + str(i+1)
           for i, c in enumerate(cases)):
        raise ValueError("Controlled case identity changed")
    if not any(row["status"] == "exception_pending" for row in plan["requirement_dispositions"]):
        raise ValueError("Exception coverage falsely closed")
    coverage = []
    for name, fragment in REQUIRED.items():
        synthetic = name in ("different_highways", "approximate_entry", "left_yields_right")
        coverage.append({"clause": name, "exact_text": fragment,
                         "authored_request_or_synthetic_measurement": synthetic,
                         "original_physical_proof": False, "legal_applicability_proven": False,
                         "case_ids": [c["case_id"] for c in cases] if synthetic else []})
    result = {"format": "c111294-2502-statutory-coverage-v1",
              "assignment_id": CASE.name, "assignment_sha256": SOURCE_SHA,
              "clauses": coverage, "source_clause_count": len(coverage),
              "original_native_observed": False, "delivery_ready": False}
    put(HERE / "statutory-coverage.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps({"source_clause_count": audit()["source_clause_count"],
                      "original_native_observed": False}))
