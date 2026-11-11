"""Source-bound original U-turn pair audit with no legal outcome inference.

The caller supplies two retained Native attempts and their independent visual
reviews. CPU fixture mode exists only for tests and is never a delivery result.
"""
import argparse
import hashlib
import json
from pathlib import Path

from process_original import process as process_intersection
from process_original_divided import process as process_divided

PAIRS = {"intersection": ("reference", "contrast"),
         "divided_opening": ("divided_reference", "divided_opening")}
FIXED_CONFIG = ("assignment_id", "assignment_sha256", "cell_id", "law_id", "actor",
                "ego_blueprint", "source_text", "frames", "rate_hz", "duration_s",
                "cameras", "camera_policy", "requested_approach_speed_mps",
                "pre_turn_dwell_s", "candidate_id")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing original pair source: " + str(path))
    return json.loads(path.read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def side(bundle, attempt, review, branch, *, synthetic_fixture):
    bundle, attempt, review = Path(bundle), Path(attempt), Path(review)
    function = process_divided if branch == "divided_opening" else process_intersection
    measured = function(bundle, attempt, review, synthetic_fixture=synthetic_fixture)
    config = read(bundle / "config.json")
    road = "divided-highway.xodr" if branch == "divided_opening" else "district-crossroads.xodr"
    frontage = bundle / "frontage-plan.json"
    require(measured["case_id"] == config["case_id"] and
            measured["candidate_id"] == config["candidate_id"] and
            measured["frames_joined"] == 800 and
            measured["raw_sha256"] == sha(attempt / "native-raw-actors.jsonl") and
            measured["review_sha256"] == sha(review),
            "Original pair result/source identity differs")
    require(measured["original_native_observed"] is (not synthetic_fixture) and
            measured["legal_verdict"] is None and measured["accepted"] is False,
            "Original pair provenance or legal status differs")
    return {"bundle": bundle, "attempt": attempt, "review": review,
            "config": config, "measured": measured,
            "road_sha256": sha(bundle / road), "frontage_sha256": sha(frontage),
            "map_sha256": sha(attempt / "native-map-readback.json"),
            "capture_sha256": sha(attempt / "native-capture-report.json")}


def audit(reference_bundle, reference_attempt, reference_review,
          contrast_bundle, contrast_attempt, contrast_review,
          branch, *, synthetic_fixture=False):
    require(branch in PAIRS, "Unknown original comparison branch")
    left = side(reference_bundle, reference_attempt, reference_review, branch,
                synthetic_fixture=synthetic_fixture)
    right = side(contrast_bundle, contrast_attempt, contrast_review, branch,
                 synthetic_fixture=synthetic_fixture)
    require(left["attempt"].resolve() != right["attempt"].resolve(),
            "Original pair reuses one attempt")
    a, b = left["config"], right["config"]
    prefix = a["assignment_id"] + "__"
    require((a["case_id"], b["case_id"]) == tuple(prefix + suffix for suffix in PAIRS[branch]),
            "Original pair case IDs differ")
    for key in FIXED_CONFIG:
        require(a.get(key) == b.get(key), "Original pair fixed condition differs: " + key)
    require(left["road_sha256"] == right["road_sha256"] and
            left["frontage_sha256"] == right["frontage_sha256"],
            "Original pair road or frontage source differs")
    require(a["requested_turn_center_x_m"] == -45.0 and
            b["requested_turn_center_x_m"] == 0.0,
            "Original pair declared location differs")
    measured_a = left["measured"]["observed_crossing_x_m"]
    measured_b = right["measured"]["observed_crossing_x_m"]
    delta = measured_b - measured_a
    require(29.0 <= delta <= 61.0,
            "Original pair observed crossing difference not resolved within request tolerances")
    field = "crossing_in_authored_opening" if branch == "divided_opening" else "crossing_in_authored_intersection_zone"
    require(left["measured"][field] is False and right["measured"][field] is True,
            "Original pair observed location classes differ")
    return {"format": "c111662-original-pair-audit-v1",
            "branch": branch, "case_ids": [a["case_id"], b["case_id"]],
            "candidate_id": a["candidate_id"],
            "source_kind": "synthetic_fixture" if synthetic_fixture else "original_native",
            "source_hashes": [{"raw": item["measured"]["raw_sha256"],
                               "review": item["measured"]["review_sha256"],
                               "map": item["map_sha256"],
                               "capture": item["capture_sha256"],
                               "road": item["road_sha256"],
                               "frontage": item["frontage_sha256"]}
                              for item in (left, right)],
            "fixed_conditions_checked": list(FIXED_CONFIG) + ["road", "frontage"],
            "observed_crossing_delta_m": delta,
            "physical_evidence_review_required": True,
            "legal_verdict": None, "accepted": False,
            "passed": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for label in ("reference", "contrast"):
        parser.add_argument("--" + label + "-bundle", required=True)
        parser.add_argument("--" + label + "-attempt", required=True)
        parser.add_argument("--" + label + "-review", required=True)
    parser.add_argument("--branch", choices=PAIRS, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = audit(args.reference_bundle, args.reference_attempt, args.reference_review,
                   args.contrast_bundle, args.contrast_attempt, args.contrast_review,
                   args.branch)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
