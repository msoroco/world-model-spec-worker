"""Review original heavy-vehicle motion and pixels after Native capture.

CPU fixtures exercise this decision logic. They cannot certify a real capture.
The lawful passing and turn premises are deliberately outside this evaluator.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from math import hypot, isfinite
from pathlib import Path


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def evaluate(report, source_audit, pixel_review, trace):
    """Return a physical event status from independently joined original sources."""
    case = report.get("case_id")
    if not isinstance(case, str) or source_audit.get("case_id") != case:
        raise ValueError("Physical case/source audit identity differs")
    if pixel_review.get("case_id") != case:
        raise ValueError("Physical case/pixel review identity differs")
    measurement = report.get("measurements", {}).get("heavy_lane_footprint", {})
    value = measurement.get("value", {})
    frames = value.get("frames")
    sources = measurement.get("sources", {})
    if not isinstance(frames, list) or not frames or len(frames) != len(trace):
        raise ValueError("Physical outcome lacks joined original frames")
    if source_audit.get("source_join_verified") is not True or source_audit.get("frames") != len(frames):
        raise ValueError("Physical outcome lacks independent source join")
    required = {"native_three_lane_survey.json", "heavy_lane_sources.jsonl",
                "trace.jsonl", "video_frames.jsonl"}
    if not required <= set(sources):
        raise ValueError("Physical outcome lacks source inventory")
    decoded = source_audit.get("four_camera_decode", {})
    if set(decoded) != set(CAMERAS):
        raise ValueError("Physical outcome lacks four original camera decodes")
    review = pixel_review.get("cameras", {})
    pixel_ok = set(review) == set(CAMERAS)
    for name in CAMERAS:
        info = decoded[name]
        if info.get("decoded_frames") != len(frames) or info.get("sha256") != sources.get(name + ".mkv"):
            raise ValueError("Physical original camera decode/source differs: " + name)
        checked = review.get(name, {})
        observations = checked.get("frames")
        frame_visibility = (isinstance(observations, list)
                            and len(observations) == len(frames)
                            and all(isinstance(row, dict)
                                    and row.get("video_frame") == index
                                    and row.get("required_markings_visible") is True
                                    and row.get("required_bodies_visible") is True
                                    for index, row in enumerate(observations)))
        pixel_ok &= (checked.get("source_sha256") == info["sha256"]
                     and checked.get("reviewed_frames") == len(frames)
                     and frame_visibility)
    progress_m = 0.0
    previous = None
    for motion, frame in zip(trace, frames):
        if (motion.get("frame"), motion.get("time_s")) != (frame.get("frame"), frame.get("time_s")):
            raise ValueError("Physical trace/frame join differs")
        point = motion.get("position", {})
        xy = (point.get("x"), point.get("y"))
        if any(not isinstance(v, (int, float)) or not isfinite(v) for v in xy):
            raise ValueError("Physical trace lacks finite position")
        if previous is not None:
            progress_m += hypot(xy[0] - previous[0], xy[1] - previous[1])
        previous = xy
        clearances = frame.get("component_clearances", [])
        if not clearances or any(not isinstance(component.get("actor_id"), int)
                                 or any(not isinstance(component.get(k), (int, float))
                                        or not isfinite(component[k])
                                        for k in ("left_clearance_m", "right_clearance_m"))
                                 for component in clearances):
            raise ValueError("Physical frame lacks full heavy-body clearances")
    inside = all(frame["minimum_clearance_m"] >= 0 for frame in frames)
    crossing = any(frame["minimum_clearance_m"] < 0 for frame in frames)
    suffix = case.rsplit("__", 1)[-1]
    if suffix.startswith("heavy_passing_plan-"):
        suffix = "passing_boundary_crossing"
    elif suffix.startswith("heavy_turn_plan-"):
        suffix = "lawful_turn_preparation_boundary_crossing"
    if suffix == "within_marked_lane":
        event = inside
    elif suffix == "unexcused_boundary_crossing":
        event = crossing
    elif suffix == "passing_boundary_crossing":
        passing = report.get("measurements", {}).get("passing_context", {}).get("value", {})
        event = (crossing and bool(passing.get("overtaken_actor_ids"))
                 and passing.get("order_reversal_observed") is True)
    elif suffix == "lawful_turn_preparation_boundary_crossing":
        turn = report.get("measurements", {}).get("turn_preparation_context", {}).get("value", {})
        plan = turn.get("turn_plan", {})
        event = (crossing and turn.get("source_frame_count") == len(frames)
                 and plan.get("requested_movement") == "turn"
                 and plan.get("direction") in ("left", "right"))
    else:
        raise ValueError("Unknown heavy-lane physical case")
    status = "unverified" if not pixel_ok else "met" if progress_m > 0.25 and event else "not_met"
    return {"case_id": case,
            "physical_checks": {"maneuver": {
                "status": status,
                "method": "source-joined full-body clearance, original trace progress, case event and four original-pixel reviews",
                "sources": sources,
                "measured_progress_m": progress_m,
                "case_event_observed": bool(event),
                "pixel_review_complete": bool(pixel_ok)}},
            "maneuver_completed": status == "met",
            "realized_observables": {"travel_progress_m": progress_m,
                                     "minimum_clearance_m": min(f["minimum_clearance_m"] for f in frames)},
            "provenance_kind": "native",
            "legal_exception_decided": False,
            "physical_acceptance_claimed": False}


def audit_saved(attempt, case_id, pixel_review, *, allow_fixture=False):
    """Join an explicit camera review to retained originals and saved measurements.

    The fixture override is only for CPU protocol tests. A real review must name
    its reviewer and Native provenance; the caller still owns visual inspection.
    """
    from delivery_audit import audit

    if not isinstance(pixel_review, dict) or pixel_review.get("case_id") != case_id:
        raise ValueError("Pixel review case identity differs")
    fixture = pixel_review.get("fixture_only") is True
    if fixture and not allow_fixture:
        raise ValueError("Synthetic pixel review cannot establish Native visibility")
    if not fixture and pixel_review.get("actual_native_capture") is not True:
        raise ValueError("Pixel review lacks actual Native capture provenance")
    if (pixel_review.get("review_method") != "frame_by_frame_originals"
            or not isinstance(pixel_review.get("reviewer_id"), str)
            or not pixel_review["reviewer_id"].strip()
            or not isinstance(pixel_review.get("reviewed_at_utc"), str)
            or not pixel_review["reviewed_at_utc"].strip()):
        raise ValueError("Pixel review lacks reviewer and method provenance")
    attempt = Path(attempt)
    joined = audit(attempt, case_id)
    report = json.loads((attempt / "analysis-report.json").read_text())
    body_rows = [json.loads(line) for line in (attempt / "heavy_lane_sources.jsonl").read_text().splitlines()
                 if line.strip()]
    heavy_ids = [{part.get("actor_id") for part in row.get("heavy_vehicle_components", [])}
                 for row in body_rows]
    if (len(body_rows) != joined["frames"] or not heavy_ids or not heavy_ids[0]
            or any(not all(isinstance(actor_id, int) for actor_id in ids)
                   or ids != heavy_ids[0] for ids in heavy_ids)):
        raise ValueError("Physical audit lacks complete heavy-body participant history")
    overtaken_ids = {row["overtaken"]["actor_id"] for row in body_rows
                     if row.get("overtaken") is not None}
    if (overtaken_ids != set(joined["passing_context"]["overtaken_actor_ids"])
            or (case_id.endswith("__passing_boundary_crossing")
                and (len(overtaken_ids) != 1 or any(row.get("overtaken") is None for row in body_rows)))
            or overtaken_ids & heavy_ids[0]):
        raise ValueError("Physical audit lacks complete overtaken participant history")
    trace = [json.loads(line) for line in (attempt / "trace.jsonl").read_text().splitlines()
             if line.strip()]
    result = evaluate(report, joined, pixel_review, trace)
    result["pixel_review_sha256"] = sha256(json.dumps(pixel_review, sort_keys=True,
                                                    separators=(",", ":")).encode()).hexdigest()
    result["pixel_reviewer_id"] = pixel_review["reviewer_id"]
    result["diagnostic_fixture"] = fixture
    result["actual_native_capture"] = not fixture
    result["audited_participant_ids"] = sorted(heavy_ids[0] | overtaken_ids)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--pixel-review", required=True)
    parser.add_argument("--allow-fixture", action="store_true")
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    review = json.loads(Path(args.pixel_review).read_text())
    outcome = audit_saved(args.attempt, args.case, review,
                          allow_fixture=args.allow_fixture)
    if args.require_complete and not outcome["maneuver_completed"]:
        parser.error("Native physical maneuver is not complete")
    print(json.dumps(outcome, indent=2, allow_nan=False))
