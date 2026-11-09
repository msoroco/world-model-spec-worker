"""Candidate-wide C111603 source-shape audit; synthetic fixtures only."""
import json

from build import CASE, HERE, write
from prove_original_processing import prove


def audit():
    results = {}
    positive = negative = 0
    for suffix in ("witness_1", "witness_2"):
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            bundle = HERE / "drafts" / suffix / candidate
            result = prove(bundle)
            if (result["positive_count"] != 1 or result["negative_count"] != 9 or
                    result["original_native_observed"] or result["delivery_ready"] or
                    not result["observed_movement_matches_request"]):
                raise ValueError("Original-shape candidate proof differs")
            results[(suffix, candidate)] = result
            positive += 1
            negative += result["negative_count"]
    for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
        turn = results[("witness_1", candidate)]
        straight = results[("witness_2", candidate)]
        if turn["observed_heading_change_deg"] < 75 or straight["observed_heading_change_deg"] > 5:
            raise ValueError("Controlled movement pair lost heading distinction")
    output = {"format": "c111603-3079a-original-shape-audit-v1",
              "assignment_id": CASE.name, "candidate_count": 8,
              "positive_count": positive, "negative_count": negative,
              "controlled_pairs": 4, "synthetic_fixture_only": True,
              "original_native_observed": False, "delivery_ready": False}
    write(HERE / "original-shape-audit.json", output)
    return output


if __name__ == "__main__":
    print(json.dumps(audit(), sort_keys=True))
