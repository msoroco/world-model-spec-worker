"""Build exact source-bound comparison inventory from frozen review context."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ASSIGNMENT = Path(__file__).resolve().parent.name
REVIEW = ROOT / "inputs" / ASSIGNMENT / "review-context" / "review.json"
OUTPUT = Path(__file__).resolve().parent / "branch-plan.json"


def build():
    raw = REVIEW.read_bytes()
    review = json.loads(raw)
    comparisons = []
    case_ids = set()
    for entry in review["comparisons"]:
        cases = []
        for case in entry["cases"]:
            case_id = case["case_id"]
            record = ROOT / "inputs" / ASSIGNMENT / "accepted" / case["recording_id"] / "metadata.json"
            metadata = json.loads(record.read_text(encoding="utf-8"))
            if metadata["case_id"] != case_id or metadata["status"] != "accepted":
                raise ValueError("review case and accepted metadata disagree")
            case_ids.add(case_id)
            cases.append({"case_id": case_id, "recording_id": case["recording_id"],
                          "authored_setting": case["description"],
                          "metadata_source": {"path": str(record.relative_to(ROOT)),
                                              "sha256": hashlib.sha256(record.read_bytes()).hexdigest()},
                          "physical_sufficiency": "unverified_from_export"})
        comparisons.append({"id": entry["id"], "cases": cases,
                            "comparison_status": "pending_original_measurement_and_independent_review"})
    expected = {"yield_nearest_view", "yield_occupied_traffic", "yield_approaching_traffic",
                "yield_across_or_within_history", "yield_slowed_or_stopped", "yield_marked_stop_line",
                "yield_near_side_marked_crosswalk", "yield_near_side_sidewalk_derived_crosswalk"}
    if {c["id"] for c in comparisons} != expected:
        raise ValueError("comparison topic coverage changed")
    if len(case_ids) != 8:
        raise ValueError("expected eight unique reviewed case identities")
    return {"assignment_id": ASSIGNMENT, "source": {"path": str(REVIEW.relative_to(ROOT)),
             "sha256": hashlib.sha256(raw).hexdigest()}, "comparisons": comparisons,
             "exact_case_ids": sorted(case_ids), "measurement_entrypoint": "nearest_view_measurement.py",
             "construction_entrypoint": "yield_control.py",
             "nearest_view_comparison_variable": "observed_conflict_response",
             "delivery_status": "partial_original_sources_unmeasured"}


if __name__ == "__main__":
    OUTPUT.write_text(json.dumps(build(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT} with eight comparisons")
