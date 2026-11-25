"""Independent original-source comparison of the two C10374 zone routes."""

import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing comparison source: " + str(path))
    return json.loads(path.read_text())


def compare(a, b, case_a, case_b):
    for label, result, case in (("A", a, case_a), ("B", b, case_b)):
        if result.get("case_id") != case or result.get("provenance_kind") != "original_native":
            raise ValueError("Missing original comparison source: " + label)
        if result.get("physical_checks", {}).get("maneuver", {}).get("status") != "met":
            raise ValueError("Incomplete original route: " + label)
        if result.get("physical_checks", {}).get("setup", {}).get("status") not in ("met", "unverified"):
            raise ValueError("Missing original zone setup source: " + label)
    fixed = ("cell_id", "law_id", "actor", "map_sha256", "camera_contract_sha256",
             "duration_s", "rate_hz", "weather_profile")
    fixed_a, fixed_b = a.get("comparison_fixed_conditions", {}), b.get("comparison_fixed_conditions", {})
    if any(key not in fixed_a or fixed_a[key] != fixed_b.get(key) for key in fixed):
        raise ValueError("Fixed comparison conditions differ")
    overlap_a = a.get("measured_values", {}).get("moving_body_rectangle_overlap_frames")
    overlap_b = b.get("measured_values", {}).get("moving_body_rectangle_overlap_frames")
    if not isinstance(overlap_a, int) or not isinstance(overlap_b, int):
        raise ValueError("Missing measured body/zone overlap")
    if overlap_a <= 0 or overlap_b != 0:
        raise ValueError("Declared overlap difference not observed")
    return {"fixed_conditions": fixed_a, "deliberate_difference": "moving_body_rectangle_overlap_frames",
            "condition_a_overlap_frames": overlap_a, "condition_b_overlap_frames": overlap_b,
            "legal_verdict_claimed": False}


def compare_capture_settings(a, b):
    fixed = ("requested_ego_speed_mps", "camera_policy", "cameras", "duration_s", "rate_hz")
    if any(key not in a or a[key] != b.get(key) for key in fixed):
        raise ValueError("Source capture settings differ")
    return {key: a[key] for key in fixed}


def selftest(case_a, case_b, negative):
    fixed = {"cell_id": "C10374", "law_id": "NRS-484B-110", "actor": "motor_vehicle_driver",
             "map_sha256": "synthetic-map", "camera_contract_sha256": "four-view",
             "duration_s": 30, "rate_hz": 20, "weather_profile": "clear"}
    def sample(case, overlap):
        return {"case_id": case, "provenance_kind": "original_native",
                "physical_checks": {"maneuver": {"status": "met"}, "setup": {"status": "met"}},
                "comparison_fixed_conditions": fixed.copy(),
                "measured_values": {"moving_body_rectangle_overlap_frames": overlap}}
    a, b = sample(case_a, 60), sample(case_b, 0)
    if negative:
        b["comparison_fixed_conditions"]["map_sha256"] = "different-map"
        compare(a, b, case_a, case_b)
        raise AssertionError("Changed map accepted")
    result = compare(a, b, case_a, case_b)
    for changed, phrase in (({"provenance_kind": "synthetic_fixture"}, "Missing original"),
                            ({"measured_values": {}}, "Missing measured")):
        modified = json.loads(json.dumps(b))
        modified.update(changed)
        try:
            compare(a, modified, case_a, case_b)
        except ValueError as error:
            assert phrase in str(error)
        else:
            raise AssertionError("Invalid comparison accepted")
    result["original_capture_attested"] = False
    return result


def check_designation(attempt, case):
    review = load(attempt / "human-review.json")
    mapping = attempt / "video_frames.jsonl"
    if (review.get("case_id") != case or review.get("source_kind") != "original_native_review"
            or not review.get("reviewer_id") or review.get("video_frames_sha256") != sha(mapping)
            or review.get("official_safety_zone_designation_verified") is not True):
        raise ValueError("Official safety-zone designation unverified")
    return sha(attempt / "human-review.json")


def main():
    p = argparse.ArgumentParser()
    for name in ("case-a", "case-b", "comparison"):
        p.add_argument("--" + name, required=True)
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--negative", action="store_true")
    p.add_argument("--attempt-a")
    p.add_argument("--attempt-b")
    p.add_argument("--output")
    args = p.parse_args()
    if args.self_test:
        print(json.dumps(selftest(args.case_a, args.case_b, args.negative), indent=2))
        return
    path_a, path_b = Path(args.attempt_a), Path(args.attempt_b)
    a, b = load(path_a / "result.json"), load(path_b / "result.json")
    result = compare(a, b, args.case_a, args.case_b)
    config_a = load(path_a / "config.json")
    config_b = load(path_b / "config.json")
    result["source_capture_settings"] = compare_capture_settings(config_a, config_b)
    result["source_config_sha256"] = [sha(path_a / "config.json"), sha(path_b / "config.json")]
    result["source_reviews_sha256"] = [check_designation(path_a, args.case_a),
                                        check_designation(path_b, args.case_b)]
    result.update(format="worker-comparison-audit", comparison_id=args.comparison,
                  case_ids=[args.case_a, args.case_b], source_result_sha256=[sha(path_a / "result.json"),
                  sha(path_b / "result.json")], physical_review_required=True)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
