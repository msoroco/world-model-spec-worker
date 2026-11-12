"""Source-bound human observation review for NRS 484B.477(2).

The statute supplies no numeric access-blocking threshold. This checker binds
reviewer observations to an independently audited attempt; it does not decide
whether the statute was violated or turn a geometry value into that decision.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from comparison_audit import load_original
from delivery_audit import require, read, sha


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LAW = "A person shall not stop, stand or park a vehicle within an alley in such position as to block the driveway or entrance to any abutting property."
REQUIRED = {
    "vehicle_action": {"native_samples.jsonl", "overview.mkv"},
    "within_alley": {"native_samples.jsonl", "road_geometry.json"},
    "access_kind": {"road_geometry.json", "property_source"},
    "abutting_property": {"road_geometry.json", "property_source"},
    "access_obstructed": {"native_samples.jsonl", "overview.mkv",
                          "reference_corner.mkv", "property_source"},
}
OPTIONS = {
    "vehicle_action": {"stop", "stand", "park", "indeterminate"},
    "within_alley": {"yes", "no", "indeterminate"},
    "access_kind": {"driveway", "entrance", "indeterminate"},
    "abutting_property": {"yes", "no", "indeterminate"},
    "access_obstructed": {"yes", "no", "indeterminate"},
}


def audit(delivery_audit_path: Path, review_path: Path, *,
          test_shape: bool = False) -> dict:
    review = read(review_path)
    case_id = review.get("case_id")
    require(case_id in {HERE.name + "__reference", HERE.name + "__contrast"},
            "Qualitative review selects another case")
    assignment = read(REPO / "inputs" / HERE.name / "assignment.json")
    require(assignment["law_record"]["text"] == LAW and
            review.get("law_input_sha256") == sha(REPO / "inputs" / HERE.name /
                                                   "assignment.json"),
            "Qualitative review law source changed")
    delivery, source = load_original(delivery_audit_path, case_id,
                                     test_shape=test_shape)
    attempt = source["attempt"]
    access = read(Path(delivery["access_review_path"]))
    property_source = Path(access["property_source"]["path"])
    bindings = {name: sha(attempt / name) for name in
                ("native_samples.jsonl", "road_geometry.json", "overview.mkv",
                 "reference_corner.mkv")}
    bindings["property_source"] = sha(property_source)
    require(review.get("format") == "c10014-qualitative-source-review" and
            (review.get("source_shaped_unit_test") is True) == test_shape and
            review.get("reviewer") and review.get("method") and
            "legal_verdict" not in review and "threshold_m" not in review and
            review.get("delivery_audit_sha256") == sha(delivery_audit_path) and
            review.get("source_sha256") == bindings and
            review.get("property_access_id") == delivery["property_access_id"],
            "Qualitative review lacks exact source bindings")
    observations = review.get("observations", {})
    require(set(observations) == set(REQUIRED),
            "Qualitative review omits a statutory observation")
    for name, needed in REQUIRED.items():
        item = observations[name]
        require(item.get("assessment") in OPTIONS[name] and
                item.get("basis") and item.get("method") and
                needed <= set(item.get("source_refs", [])) and
                set(item["source_refs"]) <= set(bindings) and
                "threshold_m" not in item and "legal_verdict" not in item,
                "Qualitative observation lacks independent sources: " + name)
    if observations["vehicle_action"]["assessment"] in {"stand", "park"}:
        purpose = Path(review.get("driver_intent_record") or "")
        require(purpose.is_file() and
                review.get("driver_intent_record_sha256") == sha(purpose),
                "Standing/parking classification lacks driver-purpose source")
    complete = all(item["assessment"] != "indeterminate"
                   for item in observations.values()) and not test_shape
    return {"format": "c10014-qualitative-source-review-audit",
            "case_id": case_id, "source_shaped_unit_test": test_shape,
            "review_completed": complete,
            "observations": {name: observations[name]["assessment"]
                             for name in REQUIRED},
            "source_sha256": bindings,
            "delivery_audit_sha256": sha(delivery_audit_path),
            "law_input_sha256": review["law_input_sha256"],
            "geometric_overlap_not_legal_threshold": True,
            "legal_verdict_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delivery-audit", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.delivery_audit, args.review)
    require(not args.output.exists(), "Retain previous qualitative review audit")
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
