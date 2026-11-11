"""Post-capture physical checks requiring original-pixel review and source joins."""

from __future__ import annotations

from math import hypot


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def check_physical_outcome(source_audit, analysis, pixel_review, trace):
    """Assess measured case realization; make no legal-exception conclusion."""
    case = analysis.get("case_id")
    if case != source_audit.get("case_id") or case != pixel_review.get("case_id"):
        raise ValueError("Physical lane outcome case identity differs")
    if source_audit.get("measurement_recomputed") is not True:
        raise ValueError("Physical lane outcome lacks independent source audit")
    frames = analysis["measurements"]["lane_boundary_observation"]["value"]["frames"]
    if len(frames) != source_audit.get("frame_count") or len(trace) != len(frames):
        raise ValueError("Physical lane outcome original frame count differs")
    cameras = source_audit.get("camera_decodes", {})
    review = pixel_review.get("cameras", {})
    if set(cameras) != set(CAMERAS) or set(review) != set(CAMERAS):
        raise ValueError("Physical lane outcome needs four reviewed original cameras")
    for name in CAMERAS:
        checked = review[name]
        if (checked.get("source_sha256") != cameras[name]["source_sha256"]
                or checked.get("reviewed_frames") != len(frames)
                or checked.get("required_markings_visible") is not True
                or checked.get("required_bodies_visible") is not True):
            raise ValueError("Missing, stale, or failed original-pixel review: " + name)
    for motion, measured in zip(trace, frames):
        if (motion.get("frame"), motion.get("time_s")) != (measured["frame"], measured["time_s"]):
            raise ValueError("Physical lane outcome trace/frame identity differs")
    first, last = trace[0]["position"], trace[-1]["position"]
    progress_m = hypot(last["x"] - first["x"], last["y"] - first["y"])
    if progress_m <= .25:
        raise ValueError("No measured lane travel progress")
    suffix = case.rsplit("__", 1)[-1]
    if suffix == "within_marked_lane":
        realized = all(row["full_footprint_inside"] for row in frames)
    elif suffix == "unexcused_boundary_crossing":
        realized = any(row["boundary_crossing"] for row in frames)
    elif suffix == "passing_boundary_crossing" or suffix.startswith("passing_excursion-"):
        value = analysis["measurements"]["lane_boundary_observation"]["value"]
        realized = any(row["boundary_crossing"] for row in frames) and value["measured_order_reversal"]
    else:
        raise ValueError("Unknown exact physical lane case")
    if not realized:
        raise ValueError("Measured lane case event not realized")
    return {"case_id": case, "measured_progress_m": progress_m,
            "measured_case_event": suffix, "original_pixel_review_bound": True,
            "physical_setup_observed": True, "legal_exception_decided": False}
