"""Compare original turn sources and measured differences for three exact cases."""

import argparse
import hashlib
import json
from pathlib import Path

from turn_native_plan import ASSIGNMENT, OFFSETS_M
from turn_position_finalizer import analyze_attempt


CAMERAS = ("overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")
FIXED = ("route_survey_original.json", "video_frames.jsonl") + CAMERAS
PHASES = {"approach": ("approach", "entry"), "departure": ("departure",)}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(directories):
    require(len(directories) == 3, "Turn comparison requires three exact attempts")
    roots = [Path(directory) for directory in directories]
    suffixes = tuple(OFFSETS_M)
    cases = [ASSIGNMENT + "__" + suffix for suffix in suffixes]
    configs = [json.loads((root / "config.json").read_text()) for root in roots]
    reports = [analyze_attempt(root, write_channels=False) for root in roots]
    bodies = [rows(root / "body_corners_original.jsonl") for root in roots]
    traces = [rows(root / "trace.jsonl") for root in roots]
    fixed_hashes = {name: [digest(root / name) for root in roots] for name in FIXED}
    for name, hashes in fixed_hashes.items():
        require(len(set(hashes)) == 1, "Turn comparison changed fixed original source: " + name)
    for name in CAMERAS:
        require(all((root / name).stat().st_size > 0 for root in roots),
                "Turn comparison lacks original camera: " + name)
    for index, (config, report, body, case, suffix) in enumerate(zip(configs, reports, bodies, cases, suffixes)):
        require(config.get("selected_case_id") == case and report.get("case_id") == case,
                "Turn comparison changed exact case identity")
        engineering = config.get("engineering", {})
        expected = OFFSETS_M[suffix]
        require((engineering.get("approach_target_offset_m"), engineering.get("departure_target_offset_m")) == expected,
                "Turn comparison changed declared target offsets")
        require(config.get("rate_hz") == 20 and config.get("duration_s") == 8 and config.get("frames") == 160,
                "Turn comparison changed capture duration")
        require(len(body) == len(bodies[0]) and [r["phase"] for r in body] == [r["phase"] for r in bodies[0]],
                "Turn comparison changed original phase inventory")
        require(len(traces[index]) == len(body), "Turn comparison trace/body count differs")
        for sample, motion in zip(body, traces[index]):
            require((sample["frame"], sample["time_s"]) == (motion["frame"], motion["time_s"]),
                    "Turn comparison trace/body identity differs")
            center = [sum(corner[axis] for corner in sample["body_corners_xy_m"]) / 4 for axis in (0, 1)]
            require(all(abs(center[axis] - motion["position_m"][axis]) < .05 for axis in (0, 1)),
                    "Turn comparison trace/body pose differs")
        if index:
            for key in ("law_id", "cell_id", "actor", "rate_hz", "duration_s", "frames", "cameras"):
                require(config.get(key) == configs[0].get(key), "Turn comparison changed fixed configuration: " + key)
    for varied, index in (("approach", 1), ("departure", 2)):
        for phase in ("approach", "entry", "departure"):
            first_rows = [row["body_corners_xy_m"] for row in bodies[0] if row["phase"] == phase]
            variant_rows = [row["body_corners_xy_m"] for row in bodies[index] if row["phase"] == phase]
            should_change = phase in PHASES[varied]
            require((first_rows != variant_rows) == should_change,
                    "Turn comparison changed wrong original body phase: " + phase)
            first_trace = [row["position_m"][:2] for row, body in zip(traces[0], bodies[0]) if body["phase"] == phase]
            variant_trace = [row["position_m"][:2] for row, body in zip(traces[index], bodies[index]) if body["phase"] == phase]
            require((first_trace != variant_trace) == should_change,
                    "Turn comparison changed wrong original trace phase: " + phase)
        fixed_index = 2 if index == 1 else 1
        for phase in PHASES[varied]:
            base_rows = [row["body_corners_xy_m"] for row in bodies[0] if row["phase"] == phase]
            other_rows = [row["body_corners_xy_m"] for row in bodies[fixed_index] if row["phase"] == phase]
            require(base_rows == other_rows, "Other comparison changed the held-fixed body phase: " + phase)
    values = [{name: item["value"] for name, item in report["measurements"].items()} for report in reports]
    require(values[0]["approach_body_to_centerline"] != values[1]["approach_body_to_centerline"]
            and values[0]["departure_body_to_left_curb"] == values[1]["departure_body_to_left_curb"],
            "Approach comparison lacks isolated measured difference")
    require(values[0]["departure_body_to_left_curb"] != values[2]["departure_body_to_left_curb"]
            and values[0]["approach_body_to_centerline"] == values[2]["approach_body_to_centerline"],
            "Departure comparison lacks isolated measured difference")
    return {"format": "worker-turn-comparison-audit", "case_ids": cases,
            "comparison_ids": ["approach_position", "departure_position"],
            "fixed_source_sha256": {name: hashes[0] for name, hashes in fixed_hashes.items()},
            "original_frames": len(bodies[0]), "controlled_original_body_differences": True,
            "measured_difference_source": "original body corners joined to source-hashed Native road geometry",
            "physical_acceptance_claimed": False, "legal_conformance": None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", action="append", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt), indent=2))
