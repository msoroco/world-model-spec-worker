"""Independent all-candidate audit of the divided original processor fixture."""
import json

from build import CASE, POLICIES, put
from divided_opening import BRANCH, CENTERS
from prove_original_divided import prove

NEGATIVES = {
    "changed_actor_id", "changed_video_frame", "changed_actor_body",
    "changed_generated_median", "changed_media", "changed_review_digest",
    "fixture_rejected_as_original",
}


def audit():
    entries = []
    for suffix in CENTERS:
        for candidate in POLICIES:
            bundle = BRANCH / "drafts" / suffix / candidate
            result = prove(bundle)
            if (result["case_id"] != CASE.name + "__" + suffix or
                    result["candidate_id"] != candidate or
                    result["positive_count"] != 1 or
                    result["negative_count"] != 7 or
                    set(result["negative_names"]) != NEGATIVES or
                    result["crossing_in_authored_opening"] !=
                    (suffix == "divided_opening") or
                    abs(result["observed_heading_change_deg"] - 180) > .001 or
                    result["original_native_observed"] or result["delivery_ready"]):
                raise ValueError("Divided original source-shape result mismatch")
            entries.append(result)
    for candidate in POLICIES:
        reference = next(row for row in entries
                         if row["candidate_id"] == candidate and
                         row["case_id"].endswith("__divided_reference"))
        opening = next(row for row in entries
                       if row["candidate_id"] == candidate and
                       row["case_id"].endswith("__divided_opening"))
        if abs(opening["observed_crossing_x_m"] -
               reference["observed_crossing_x_m"] - 45) > .0002:
            raise ValueError("Divided source-shape controlled pair changed")
    result = {
        "format": "c111662-4033-divided-original-shape-audit-v1",
        "candidate_count": len(entries), "positive_count": len(entries),
        "negative_count": sum(row["negative_count"] for row in entries),
        "controlled_pairs": len(POLICIES), "entries": entries,
        "synthetic_fixture_only": True, "original_native_observed": False,
        "delivery_ready": False}
    put(BRANCH / "original-shape-audit.json", result)
    return result


if __name__ == "__main__":
    result = audit()
    print(json.dumps({key: result[key] for key in
                      ("candidate_count", "positive_count", "negative_count",
                       "controlled_pairs")}))
