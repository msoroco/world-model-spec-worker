"""Compare original ordinary-device and contrary-officer response sources."""
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
            raise ValueError("Incomplete original device response: " + label)
        if result.get("physical_checks", {}).get("setup", {}).get("status") != "met":
            raise ValueError("Missing original device/officer source: " + label)
    fixed = ("cell_id", "law_id", "actor", "road_sha256", "device_id",
             "camera_policy", "camera_sources", "officer_position_xy_m",
             "requested_speed_mps", "duration_s", "rate_hz")
    fa, fb = a.get("comparison_fixed_conditions", {}), b.get("comparison_fixed_conditions", {})
    if any(key not in fa or fa[key] != fb.get(key) for key in fixed):
        raise ValueError("Fixed comparison conditions differ")
    ra = a.get("measured_values", {}).get("device_response", {})
    rb = b.get("measured_values", {}).get("device_response", {})
    if (ra.get("stopped_before_device") is not True or ra.get("crossed_device_station") is not False
            or ra.get("reviewed_direction") != "none_contrary"
            or rb.get("crossed_device_station") is not True
            or rb.get("reviewed_direction") != "proceed"):
        raise ValueError("Declared device/Officer response difference not observed")
    return {"fixed_conditions": {key: fa[key] for key in fixed},
            "deliberate_difference": "requested and reviewed officer direction",
            "ordinary_device_response": ra, "contrary_officer_response": rb,
            "legal_verdict_claimed": False}


def selftest(case_a, case_b, negative):
    fixed = {"cell_id": "C10365", "law_id": "LVMC-11-40-070",
             "actor": "cycle_or_scooter_operator", "road_sha256": "synthetic-road",
             "device_id": "3651", "camera_policy": "four-view", "camera_sources": {},
             "officer_position_xy_m": [39, -8], "requested_speed_mps": 4,
             "duration_s": 30, "rate_hz": 20}
    def sample(case, response):
        return {"case_id": case, "provenance_kind": "original_native",
                "physical_checks": {"maneuver": {"status": "met"}, "setup": {"status": "met"}},
                "comparison_fixed_conditions": fixed.copy(),
                "measured_values": {"device_response": response}}
    a = sample(case_a, {"stopped_before_device": True,
                        "crossed_device_station": False, "reviewed_direction": "none_contrary"})
    b = sample(case_b, {"stopped_before_device": False,
                        "crossed_device_station": True, "reviewed_direction": "proceed"})
    if negative:
        b["comparison_fixed_conditions"]["road_sha256"] = "different-road"
        compare(a, b, case_a, case_b)
        raise AssertionError("Changed road accepted")
    result = compare(a, b, case_a, case_b)
    for change, fragment in (({"provenance_kind": "synthetic_fixture"}, "Missing original"),
                             ({"measured_values": {}}, "Declared device")):
        altered = json.loads(json.dumps(b))
        altered.update(change)
        try:
            compare(a, altered, case_a, case_b)
        except ValueError as error:
            assert fragment in str(error)
        else:
            raise AssertionError("Invalid comparison accepted")
    result["original_capture_attested"] = False
    return result


def main():
    parser = argparse.ArgumentParser()
    for name in ("case-a", "case-b", "comparison"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--negative", action="store_true")
    parser.add_argument("--attempt-a")
    parser.add_argument("--attempt-b")
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(selftest(args.case_a, args.case_b, args.negative), indent=2))
        return
    path_a, path_b = Path(args.attempt_a), Path(args.attempt_b)
    a, b = load(path_a / "result.json"), load(path_b / "result.json")
    result = compare(a, b, args.case_a, args.case_b)
    reviews = [load(path_a / "review.json"), load(path_b / "review.json")]
    for review, case in zip(reviews, (args.case_a, args.case_b)):
        if (review.get("source_kind") != "original_native_review"
                or review.get("case_id") != case or review.get("device_applicable") is not True
                or not review.get("reviewer")):
            raise ValueError("Missing independent original device review")
    if reviews[1].get("officer_authority_reviewed") is not True or reviews[1].get("direction_visible") is not True:
        raise ValueError("Police Officer contrary direction unverified")
    result.update(format="worker-comparison-audit", comparison_id=args.comparison,
                  case_ids=[args.case_a, args.case_b],
                  source_result_sha256=[sha(path_a / "result.json"), sha(path_b / "result.json")],
                  source_review_sha256=[sha(path_a / "review.json"), sha(path_b / "review.json")],
                  physical_review_required=True)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
