"""Independent original-source comparison for each statutory-position pair."""

import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def original_result(attempt, case):
    folder = Path(attempt).resolve()
    result = read(folder / "result.json")
    survey_path = folder / "context-survey.json"
    survey = read(survey_path)
    config = read(folder / "config.json")
    review = read(folder / "independent-review.json")
    if (result.get("case_id") != case or
            survey.get("source_kind") != "original_native_context_survey" or
            review.get("format") != "worker-nrs280-independent-source-review-v1" or
            review.get("case_id") != case or
            not review.get("actual_driver_observation_source_reviewed") or
            config.get("selected_case_id") != case):
        raise ValueError("Comparison lacks independently reviewed original source")
    facts = dict(result.get("measured_values", {}))
    facts.update(pedestrian_source_identity=sha(survey_path),
                 approach_source_identity=sha(survey_path),
                 visibility_review_protocol=review["format"],
                 driver_observation_review_protocol=review["format"],
                 capture_profile=json.dumps({"rate_hz": config.get("rate_hz"),
                                             "duration_s": config.get("duration_s"),
                                             "cameras": config.get("cameras")}, sort_keys=True),
                 requested_control_policy=config.get("mode"))
    return dict(result, measured_values=facts)


def check(left, right, comparison):
    cases = comparison["case_ids"]
    if (left.get("case_id") != cases[0] or right.get("case_id") != cases[1]
            or left.get("provenance_kind") != "native"
            or right.get("provenance_kind") != "native"
            or left.get("diagnostic_fixture") is not False
            or right.get("diagnostic_fixture") is not False):
        raise ValueError("Comparison lacks two original exact-case Native sources")
    if (left.get("accepted") is not False or right.get("accepted") is not False
            or left.get("legal_verdict_claimed") is not False
            or right.get("legal_verdict_claimed") is not False):
        raise ValueError("Comparison prelabels the legal outcome")
    first, second = left.get("measured_values", {}), right.get("measured_values", {})
    fixed = ("branch", "pedestrian_source_identity", "approach_source_identity",
             "visibility_review_protocol", "driver_observation_review_protocol",
             "capture_profile")
    if any(first.get(key) is None or first.get(key) != second.get(key) for key in fixed):
        raise ValueError("Undeclared comparison source difference")
    if (first.get("frames") != 600 or second.get("frames") != 600
            or first.get("first_actual_observation_frame") is None
            or second.get("first_actual_observation_frame") is None):
        raise ValueError("Comparison lacks joined original observation")
    if first.get("requested_control_policy") == second.get("requested_control_policy"):
        raise ValueError("Comparison lacks requested-control contrast")
    if comparison.get("deliberate_differences") != ["post_observation_ego_speed_request"]:
        raise ValueError("Comparison changed the declared difference")
    return {"comparison_id": comparison["comparison_id"], "case_ids": cases,
            "source_branch": comparison["source_branch"],
            "requested_control_contrast": [first["requested_control_policy"],
                                           second["requested_control_policy"]],
            "legal_verdict_claimed": False}


def selftest(comparison, negative):
    common = {"provenance_kind": "native", "diagnostic_fixture": False,
              "accepted": False, "legal_verdict_claimed": False,
              "measured_values": {"branch": comparison["comparison_id"],
                                  "pedestrian_source_identity": "original position survey",
                                  "approach_source_identity": "original approach survey",
                                  "visibility_review_protocol": "independent review",
                                  "driver_observation_review_protocol": "independent review",
                                  "capture_profile": "600 frames, 20 Hz, four cameras",
                                  "frames": 600, "first_actual_observation_frame": 150,
                                  "requested_control_policy": "caution"}}
    left = json.loads(json.dumps(common))
    right = json.loads(json.dumps(common))
    left["case_id"], right["case_id"] = comparison["case_ids"]
    right["measured_values"]["requested_control_policy"] = "maintain"
    if negative:
        right["measured_values"]["pedestrian_source_identity"] = "different source"
        check(left, right, comparison)
        raise AssertionError("Changed original position source accepted")
    result = check(left, right, comparison)
    for key, value in (("provenance_kind", "synthetic_fixture"),
                       ("accepted", True), ("legal_verdict_claimed", True)):
        changed = json.loads(json.dumps(right))
        changed[key] = value
        try:
            check(left, changed, comparison)
        except ValueError:
            pass
        else:
            raise AssertionError("Unreviewed comparison accepted: " + key)
    return dict(result, original_capture_attested=False, source_predicates_tested=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--negative", action="store_true")
    parser.add_argument("--left")
    parser.add_argument("--right")
    parser.add_argument("--output")
    args = parser.parse_args()
    plan = read(Path(__file__).with_name("case-plan.json"))
    comparison = next((row for row in plan["comparisons"]
                       if row["comparison_id"] == args.comparison), None)
    if comparison is None:
        raise ValueError("Unknown exact comparison")
    if args.self_test:
        result = selftest(comparison, args.negative)
    else:
        result = check(original_result(args.left, comparison["case_ids"][0]),
                       original_result(args.right, comparison["case_ids"][1]), comparison)
        result.update(format="worker-nrs280-original-comparison-audit-v1",
                      left_sha256=sha(Path(args.left) / "result.json"),
                      right_sha256=sha(Path(args.right) / "result.json"),
                      auditor_sha256=sha(__file__))
        Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
