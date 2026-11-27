"""Independently compare the selected synthetic duration boundary probes."""

import argparse
import hashlib
import json
from pathlib import Path

from duration_policy import TARGETS, TOTAL_FRAMES, comparison_invariants


HERE = Path(__file__).resolve().parent.parent
AID = HERE.name
ASSIGNMENT = AID
HELD = ("road_sha256", "device_review_sha256", "parking_review_sha256",
        "street_review_sha256", "civil_clock_review_sha256",
        "camera_policy_sha256", "weather", "parking_target_xy_m")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_reports(paths):
    if set(paths) != set(TARGETS):
        raise ValueError("Exact duration triple required")
    reports = {suffix: json.loads(Path(path).read_text()) for suffix, path in paths.items()}
    held = {key: reports["below_30"].get(key) for key in HELD}
    for suffix, target in TARGETS.items():
        report = reports[suffix]
        if report.get("case_id") != AID + "__" + suffix or report.get("requested_duration_s") != target:
            raise ValueError("Duration target changed")
        if report.get("capture_frames") != TOTAL_FRAMES or report.get("rate_hz") != 20:
            raise ValueError("Incomplete duration capture")
        if any(report.get(key) != value for key, value in held.items()):
            raise ValueError("Duration comparison changed held condition")
        if report.get("stationary_duration_ms") != target * 1000:
            raise ValueError("Measured duration differs")
        for source in report.get("sources", {}).values():
            path = Path(paths[suffix]).parent / source["path"]
            if not path.is_file():
                raise ValueError("Comparison source missing")
            if digest(path) != source["sha256"]:
                raise ValueError("Comparison source hash differs")
    return {"held_conditions": list(HELD), "physical_or_legal_acceptance": False}


def audit_selected(negative=False):
    configs = {}
    measured = {}
    construction_hashes = {}
    for suffix, target in TARGETS.items():
        construction_path = HERE / ("construction.json" if suffix == "below_30" else
                                    "cases/" + suffix + "/construction.json")
        construction = json.loads(construction_path.read_text())
        configs[suffix] = json.loads(next(item["content"] for item in construction["files"]
                                           if item["path"] == "config.json"))
        construction_hashes[suffix] = digest(construction_path)
        result_path = HERE / "physical" / suffix / "complete_motion-result.json"
        result = json.loads(result_path.read_text())
        observed = result.get("realized_observables", {}).get("night_parking_duration_ms")
        if result.get("diagnostic_fixture") is not True or observed != target * 1000:
            raise ValueError("Full-length synthetic duration probe differs")
        measured[suffix] = observed
    if negative:
        configs["above_30"]["weather"] = {"tampered": True}
    invariants = comparison_invariants(configs)
    if not (measured["below_30"] < 1800000 == measured["at_30"]
            < measured["above_30"] and
            all(config["capture_frames"] == TOTAL_FRAMES for config in configs.values())):
        raise ValueError("Strict thirty-minute bracket absent")
    return {"format": "c229398-duration-comparison-audit-v1",
            "comparison_id": AID + "__duration_boundary", "passed": True,
            "case_ids": [AID + "__" + suffix for suffix in TARGETS],
            "construction_sha256": construction_hashes,
            "held_fields": invariants["held_fields"],
            "duration_ms": measured, "diagnostic_fixture": True,
            "original_native_executed": False,
            "physical_or_legal_acceptance": False}


def audit(paths=None):
    return audit_reports(paths) if paths is not None else audit_selected()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-selftest", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit_selected(args.negative_selftest), sort_keys=True))


if __name__ == "__main__":
    main()
