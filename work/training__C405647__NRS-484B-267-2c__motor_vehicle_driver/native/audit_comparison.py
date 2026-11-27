"""Independent saved-source check of the two emergency approach requests.

This reports engineering observations, never a legal preparedness verdict.
"""

import argparse
import json
from pathlib import Path

from measure_readiness import ASSIGNMENT, lines, measure, sha
from scene import CASES, request


def audit(roots, reported):
    if set(roots) != set(CASES) or set(reported) != set(CASES):
        raise ValueError("Both exact comparison conditions are required")
    plans = {condition: request(condition) for condition in CASES}
    fixed = set(plans[CASES[0]]) - {"case_id", "ego_response_policy", "requested_setting"}
    for key in fixed:
        if plans[CASES[0]][key] != plans[CASES[1]][key]:
            raise ValueError("Comparison construction changed fixed condition: " + key)
    if plans[CASES[0]]["ego_response_policy"] == plans[CASES[1]]["ego_response_policy"]:
        raise ValueError("Comparison has no requested brake-response contrast")
    observed = {}
    request_hashes = {}
    for condition in CASES:
        root = Path(roots[condition])
        request_path = root / "native-request.json"
        if not request_path.is_file() or json.loads(request_path.read_text()) != plans[condition]:
            raise ValueError("Original attempt request differs from exact construction: " + condition)
        request_hashes[condition] = sha(request_path)
        actual = measure(root)
        supplied = json.loads(Path(reported[condition]).read_text())
        if actual != supplied:
            raise ValueError("Reported observation differs from saved sources: " + condition)
        if actual["assignment_id"] != ASSIGNMENT or actual["legal_verdict_claimed"]:
            raise ValueError("Invalid assignment or legal claim")
        observed[condition] = actual
    a, b = (observed[x] for x in CASES)
    path_a, path_b = (Path(roots[x]) for x in CASES)
    frame_a, frame_b = (lines(path / "video_frames.jsonl") for path in (path_a, path_b))
    trace_a, trace_b = (lines(path / "approach_trace.jsonl") for path in (path_a, path_b))
    for index, (left, right, lrow, rrow) in enumerate(zip(frame_a, frame_b, trace_a, trace_b)):
        if left["time_s"] != right["time_s"]:
            raise ValueError("Comparison changed capture cadence at frame " + str(index))
        for key in ("emergency_speed_mps", "emergency_flashing_visible",
                    "emergency_motion_visible", "hand_signal_visible"):
            if lrow[key] != rrow[key]:
                raise ValueError("Comparison changed emergency trajectory or indication: " + key)
    review_a, review_b = (json.loads((path / "emergency_review.json").read_text())
                          for path in (path_a, path_b))
    for key in ("vehicle_class", "lights_meet_484A_480_3",
                "visible_to_approaching_driver", "officer_direction_present"):
        if review_a[key] != review_b[key]:
            raise ValueError("Comparison changed reviewed legal context: " + key)
    if a["source_kind"] != b["source_kind"]:
        raise ValueError("Comparison source provenance differs")
    for key in ("trigger_frame", "trigger_time_s", "trigger_gap_m",
                "trigger_ego_speed_mps", "emergency_moving_at_trigger",
                "emergency_motion_visible_at_trigger", "hand_signal_visible_at_trigger",
                "flashing_visible_at_trigger", "lights_meet_484A_480_3_reviewed",
                "officer_direction_present_reviewed", "sample_count", "sample_span_s"):
        if a[key] != b[key]:
            raise ValueError("Comparison changed measured trigger context: " + key)
    if a["officer_direction_present_reviewed"]:
        raise ValueError("Officer-direction exception requires a separate branch")
    if a["first_brake_frame"] is None or b["first_brake_frame"] is not None:
        raise ValueError("Measured brake-response contrast absent")
    return {"format": "emergency-readiness-comparison-audit",
            "assignment_id": ASSIGNMENT, "case_ids": [plans[x]["case_id"] for x in CASES],
            "source_hashes": {x: observed[x]["sources"] for x in CASES},
            "native_request_sha256": request_hashes,
            "fixed_trigger_context_checked": True,
            "full_emergency_trajectory_and_context_checked": True,
            "observed_brake_frames": {x: observed[x]["first_brake_frame"] for x in CASES},
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for condition in CASES:
        parser.add_argument("--" + condition.replace("_", "-"), required=True)
        parser.add_argument("--" + condition.replace("_", "-") + "-observation", required=True)
    args = vars(parser.parse_args())
    roots = {condition: args[condition] for condition in CASES}
    reports = {condition: args[condition + "_observation"] for condition in CASES}
    print(json.dumps(audit(roots, reports), indent=2, sort_keys=True))
