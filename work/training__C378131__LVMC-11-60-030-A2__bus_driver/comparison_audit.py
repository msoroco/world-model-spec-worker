"""Check controlled bus comparisons from two independently audited sources."""

import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from analysis.saved_only import extract

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare(left, right, difference, *, fixture=False):
    kind = "synthetic_native_sample" if fixture else "original_native_bus_readback"
    for report in (left, right):
        if report.get("source_kind") != kind or not report.get("source_audit_sha256"):
            raise ValueError("independent source audit missing")
        if not fixture and (report.get("physical_completion") != "reviewed_original" or
                            not report.get("designation_authority_source_sha256") or
                            not report.get("actual_loading_review_sha256")):
            raise ValueError("original physical, loading or authority review missing")
    for key in ("route_id_requested", "street_id", "cell_id", "weather_id",
                "controller_id", "loading_purpose", "capture_profile"):
        if left.get(key) is None or left[key] != right.get(key):
            raise ValueError("fixed condition differs: " + key)
    keys = ("zone_kind_requested", "emergency_requested", "vehicle_class_requested")
    if difference not in keys:
        raise ValueError("undeclared comparison variable")
    for key in keys:
        if key == difference and left[key] == right[key]:
            raise ValueError("declared difference absent: " + key)
        if key != difference and left[key] != right[key]:
            raise ValueError("undeclared difference: " + key)
    return {"format": "bus-independent-comparison-audit", "passed": True,
            "difference": difference, "fixed_conditions_checked": ["route_id_requested",
            "street_id", "cell_id", "weather_id", "controller_id", "loading_purpose",
            "capture_profile"], "source_audits": [left["source_audit_sha256"],
            right["source_audit_sha256"]], "physical_acceptance_claimed": False,
            "legal_outcome": "unresolved"}


def fixture_report(slug, temporary):
    source = HERE / "selected-source" / slug
    measurement = extract(source, Path(temporary) / (slug + ".json"), fixture=True)
    return dict(measurement, street_id="bus-c378131-street", cell_id="C378131",
                weather_id="clear", controller_id="bus-curb-controller-v1",
                loading_purpose="passenger_exchange_requested",
                capture_profile="four-view-600-frame-20hz")


def selftest(comparison_id, negative=False):
    plan = json.loads((HERE / "case-plan.json").read_text())
    comparison = next((item for item in plan["comparisons"]
                       if item["comparison_id"] == comparison_id), None)
    if comparison is None:
        raise ValueError("Unknown exact comparison")
    left_slug, right_slug = [case.removeprefix(HERE.name + "__")
                             for case in comparison["case_ids"]]
    with tempfile.TemporaryDirectory(prefix="bus-comparison-test-") as temporary:
        left = fixture_report(left_slug, temporary)
        right = fixture_report(right_slug, temporary)
        difference = {"loading_location": "zone_kind_requested",
                      "emergency_context": "emergency_requested",
                      "vehicle_class": "vehicle_class_requested"}[
                          comparison["deliberate_differences"][0]]
        if negative:
            right[difference] = left[difference]
        result = compare(left, right, difference, fixture=True)
        result["comparison_id"] = comparison_id
        result["scope"] = "synthetic source mechanics only"
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--negative-selftest", action="store_true")
    parser.add_argument("--left-review")
    parser.add_argument("--right-review")
    args = parser.parse_args()
    if args.selftest or args.negative_selftest:
        result = selftest(args.comparison, negative=args.negative_selftest)
    else:
        if not args.left_review or not args.right_review:
            raise ValueError("two independent original review reports required")
        plan = json.loads((HERE / "case-plan.json").read_text())
        item = next(row for row in plan["comparisons"] if row["comparison_id"] == args.comparison)
        difference = {"loading_location": "zone_kind_requested",
                      "emergency_context": "emergency_requested",
                      "vehicle_class": "vehicle_class_requested"}[item["deliberate_differences"][0]]
        result = compare(json.loads(Path(args.left_review).read_text()),
                         json.loads(Path(args.right_review).read_text()), difference)
        result["comparison_id"] = args.comparison
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
