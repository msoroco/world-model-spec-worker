"""Independent original-source comparison of governed and adjacent lane travel."""
import argparse
import json
from pathlib import Path

from delivery_audit import ASSIGNMENT, audit_delivery, audit_structure, require, rows, sha, source

CASE_A = ASSIGNMENT + "__selected_378a10ff__condition_a"
CASE_B = ASSIGNMENT + "__selected_378a10ff__condition_b"


def compare_structure(first_attempt, second_attempt, first_hashes, second_hashes):
    first = Path(first_attempt).resolve()
    second = Path(second_attempt).resolve()
    require(first != second, "Independent original attempts required")
    left = audit_structure(first, CASE_A, first_hashes)
    right = audit_structure(second, CASE_B, second_hashes)
    require(left["target_lane_id"] == -1 and right["target_lane_id"] == -2,
            "Declared governed versus adjacent lane contrast absent")
    require(left["governed_lane_id"] == right["governed_lane_id"] == -1,
            "Fixed signal-governed lane changed")
    require(first_hashes["native-map-readback.xodr"] == second_hashes["native-map-readback.xodr"],
            "Fixed original road and signal inventory changed")
    a_rows = rows(source(first, "native-signal-rows.jsonl"))
    b_rows = rows(source(second, "native-signal-rows.jsonl"))
    require(all(a["signal"] == b["signal"] for a, b in zip(a_rows, b_rows)),
            "Original arrow state, mount or signal authority changed")
    require(left["facing_green_proposed_frames"] == 600 and
            right["facing_green_proposed_frames"] == 0,
            "Observed governed versus adjacent arrow-lane contrast absent")
    a_config = json.loads(source(first, "config.json").read_text())
    b_config = json.loads(source(second, "config.json").read_text())
    fixed = ("law_id", "cell_id", "actor", "rate_hz", "duration_s", "cameras")
    require(all(a_config.get(key) == b_config.get(key) for key in fixed),
            "Fixed actor, duration, cameras or scenario context changed")
    return {"format": "c230247-source-comparison-v1", "passed": True,
        "case_ids": [CASE_A, CASE_B],
        "fixed_checks": {"same_original_map": True, "same_arrow_state": True,
            "same_actor_duration_and_cameras": True},
        "deliberate_difference": "target_lane_id",
        "observed_lane_ids": [-1, -2],
        "facing_green_proposed_frames": [600, 0],
        "source_hashes": [first_hashes, second_hashes],
        "legal_verdict": None,
        "adjacent_lane_prohibition_claimed": False}


def compare_delivery(first_attempt, second_attempt, first_review, second_review):
    a = audit_delivery(first_attempt, CASE_A, first_review)
    b = audit_delivery(second_attempt, CASE_B, second_review)
    result = compare_structure(first_attempt, second_attempt,
                               first_review["source_sha256"], second_review["source_sha256"])
    result.update({"format": "c230247-reviewed-original-comparison-v1",
        "delivery_audit_sha256": [sha(Path(first_review["review_path"])),
                                  sha(Path(second_review["review_path"]))],
        "reviewed_recording_ids": [a["recording_id"], b["recording_id"]]})
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition-a", required=True)
    parser.add_argument("--condition-b", required=True)
    parser.add_argument("--review-a", required=True)
    parser.add_argument("--review-b", required=True)
    parser.add_argument("--structure-only", action="store_true")
    args = parser.parse_args()
    a = json.loads(Path(args.review_a).read_text())
    b = json.loads(Path(args.review_b).read_text())
    if args.structure_only:
        result = compare_structure(args.condition_a, args.condition_b,
                                   a["source_sha256"], b["source_sha256"])
    else:
        a["review_path"] = args.review_a
        b["review_path"] = args.review_b
        result = compare_delivery(args.condition_a, args.condition_b, a, b)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
