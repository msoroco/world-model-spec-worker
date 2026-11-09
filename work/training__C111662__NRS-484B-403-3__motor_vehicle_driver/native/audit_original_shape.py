"""Independent CPU audit of all original-processor synthetic source-shape fixtures."""
import json

from build import CASE, CASES, HERE, POLICIES, put
from prove_original_processing import prove

EXPECTED_NEGATIVES = {
    "changed_actor_id", "changed_video_frame", "changed_actor_body",
    "changed_generated_lane", "changed_media", "changed_review_digest",
    "fixture_rejected_as_original",
}


def audit():
    entries = []
    for suffix in CASES:
        for candidate in POLICIES:
            bundle = HERE / "drafts" / suffix / candidate
            result = prove(bundle)
            if (result["case_id"] != CASE.name + "__" + suffix or
                    result["candidate_id"] != candidate or
                    result["positive_count"] != 1 or result["negative_count"] != 7 or
                    set(result["negative_names"]) != EXPECTED_NEGATIVES or
                    result["crossing_in_authored_intersection_zone"] != (suffix == "contrast") or
                    abs(result["observed_heading_change_deg"] - 180) > .001 or
                    result["original_native_observed"] or result["delivery_ready"]):
                raise ValueError("Original-processor source-shape result mismatch")
            entries.append(result)
    for candidate in POLICIES:
        reference = next(x for x in entries if x["candidate_id"] == candidate
                         and x["case_id"].endswith("__reference"))
        contrast = next(x for x in entries if x["candidate_id"] == candidate
                        and x["case_id"].endswith("__contrast"))
        if abs(contrast["observed_crossing_x_m"] - reference["observed_crossing_x_m"] - 45) > .0002:
            raise ValueError("Controlled source-shape crossing delta changed")
    result = {"format": "c111662-4033-original-shape-audit-v1",
              "candidate_count": len(entries), "positive_count": len(entries),
              "negative_count": sum(x["negative_count"] for x in entries),
              "controlled_pairs": len(POLICIES), "entries": entries,
              "synthetic_fixture_only": True, "original_native_observed": False,
              "delivery_ready": False}
    put(HERE / "original-shape-audit.json", result)
    return result


if __name__ == "__main__":
    result = audit()
    print(json.dumps({key: result[key] for key in
                      ("candidate_count", "positive_count", "negative_count", "controlled_pairs")}))
