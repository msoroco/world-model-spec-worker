"""Independent source-bound comparison of nighttime parking durations."""

import argparse
import hashlib
import json
from pathlib import Path

from duration_policy import TARGETS, TOTAL_FRAMES


ASSIGNMENT = "training__C229398__LVMC-11-52-300__nonmotor_vehicle_operator"
HELD = ("road_sha256", "device_review_sha256", "parking_review_sha256",
        "street_review_sha256", "civil_clock_review_sha256", "camera_policy_sha256",
        "weather", "parking_target_xy_m", "capture_frames", "rate_hz")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(report_paths):
    if set(report_paths) != set(TARGETS):
        raise ValueError("Exact duration boundary triple missing")
    reports = {}
    for suffix, path in report_paths.items():
        path = Path(path).resolve()
        report = json.loads(path.read_text())
        if report.get("format") != "c229398-measured-duration-report-v1" or report.get(
                "case_id") != ASSIGNMENT + "__" + suffix:
            raise ValueError("Wrong exact measured case")
        if report.get("capture_frames") != TOTAL_FRAMES or report.get("rate_hz") != 20:
            raise ValueError("Incomplete duration capture")
        if report.get("provenance_kind") not in ("synthetic_fixture", "original_native"):
            raise ValueError("Measured report provenance unresolved")
        if not isinstance(report.get("stationary_duration_ms"), int) or report[
                "stationary_duration_ms"] < 0:
            raise ValueError("Missing measured parking duration")
        sources = report.get("sources")
        if not isinstance(sources, dict) or set(sources) != {
                "frame_map", "actor_motion", "source_review", "camera_frame_map"}:
            raise ValueError("Missing independent duration sources")
        for name, row in sources.items():
            if not isinstance(row, dict) or not row.get("path") or not row.get("sha256"):
                raise ValueError("Missing source binding: " + name)
            relative = Path(row["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Unsafe source path: " + name)
            source_path = (path.parent / relative).resolve()
            if path.parent not in source_path.parents or not source_path.is_file():
                raise ValueError("Comparison source missing: " + name)
            if digest(source_path) != row["sha256"]:
                raise ValueError("Comparison source hash differs: " + name)
        if any(not report.get(field) for field in HELD):
            raise ValueError("Held comparison condition missing")
        reports[suffix] = report
    first = reports["below_30"]
    for suffix, report in reports.items():
        if any(report[field] != first[field] for field in HELD):
            raise ValueError("Duration comparison changed held condition: " + suffix)
        if report.get("requested_duration_s") != TARGETS[suffix]:
            raise ValueError("Requested duration target changed: " + suffix)
    return {"format": "c229398-independent-comparison-audit-v1",
            "case_ids": [ASSIGNMENT + "__" + suffix for suffix in TARGETS],
            "report_sha256": {suffix: digest(report_paths[suffix]) for suffix in TARGETS},
            "measured_stationary_duration_ms": {suffix: reports[suffix][
                "stationary_duration_ms"] for suffix in TARGETS},
            "held_conditions": list(HELD),
            "deliberate_difference": "requested stop frame / measured stationary duration",
            "physical_or_legal_acceptance": False}


def main():
    parser = argparse.ArgumentParser()
    for suffix in TARGETS:
        parser.add_argument("--" + suffix.replace("_", "-"), required=True)
    args = parser.parse_args()
    paths = {suffix: getattr(args, suffix) for suffix in TARGETS}
    print(json.dumps(audit(paths)))


if __name__ == "__main__":
    main()
