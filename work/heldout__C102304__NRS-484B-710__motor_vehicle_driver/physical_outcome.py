"""Independent post-capture outcome check for NRS 484B.710.

Fixture tests exercise the logic; only original pixel review can satisfy a real attempt.
"""

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")

def check_physical_outcome(source_audit, analysis, pixel_review, *, target_ft,
                           attainment_band_ft=2.0):
    """Check recorded motion and a separately reviewed original-pixel inventory.

    The band is an engineering attainment check, never a legal cutoff. The
    caller must supply a review of actual source pixels after capture; a fixture
    can test this logic but cannot supply a real visibility finding.
    """
    if source_audit.get("case_id") != analysis.get("case_id"):
        raise ValueError("Physical outcome case identity differs")
    observation = analysis["measurements"]["fire_boundary_observation"]["value"]
    if observation["active_frame_count"] <= 0:
        raise ValueError("No measured active branch frames")
    if observation["frame_count"] != source_audit.get("frame_count"):
        raise ValueError("Physical outcome frame count differs")
    if pixel_review.get("case_id") != analysis["case_id"]:
        raise ValueError("Pixel review case identity differs")
    cameras = source_audit["camera_decodes"]
    reviews = pixel_review.get("cameras")
    if not isinstance(reviews, dict) or set(reviews) != set(CAMERAS):
        raise ValueError("Pixel review omits a source camera")
    for name in CAMERAS:
        review = reviews[name]
        if (review.get("source_sha256") != cameras[name]["source_sha256"]
                or review.get("reviewed_frames") != source_audit["frame_count"]
                or review.get("required_bodies_visible") is not True):
            raise ValueError("Missing, stale, or failed original-pixel review: " + name)
    if pixel_review.get("alarm_premise_source_reviewed") is not True:
        raise ValueError("Alarm-response premise has no source review")
    if observation["branch"] == "traveling_follow" and (
            observation["exception_context"]["authorized_emergency"] or
            observation["exception_context"]["official_business"]):
        if pixel_review.get("authorization_source_reviewed") is not True:
            raise ValueError("Emergency authorization premise has no source review")
        if pixel_review.get("official_business_source_reviewed") is not True:
            raise ValueError("Official-business premise has no source review")
    measured = observation["min_boundary_distance_ft"]
    if abs(measured - target_ft) > attainment_band_ft:
        raise ValueError("Measured boundary missed engineering attainment band")
    return {"case_id": analysis["case_id"], "branch": observation["branch"],
            "measured_boundary_ft": measured, "target_ft": target_ft,
            "attainment_band_ft": attainment_band_ft,
            "active_frame_count": observation["active_frame_count"],
            "original_pixel_review_bound": True,
            "legal_conclusion": None}

