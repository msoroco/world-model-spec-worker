"""Summarize source-bound sight-line samples for NRS 484B.407.

This module reports geometry only. It cannot decide what a real driver sees or
whether a U-turn violates the statute.
"""

from typing import Mapping


STATUTORY_DISTANCE_M = 500 * 0.3048
REQUIRED_DIRECTIONS = ("approach_a", "approach_b")


def summarize(samples_by_direction: Mapping[str, list[dict]]) -> dict:
    """Require both approach inventories; retain clearance and obstruction bounds.

    Samples contain `distance_m` from the maneuver site, `visible` for the
    virtual-observer proxy, and a nonempty `source_ref`. A sample beyond 500
    feet establishes only inventory extent. Sparse sampling leaves an interval,
    never an invented exact occluder or continuous visibility conclusion.
    """
    if set(samples_by_direction) != set(REQUIRED_DIRECTIONS):
        raise ValueError("both inventoried approach directions are required")
    output = {"statutory_distance_m": STATUTORY_DISTANCE_M, "directions": {}}
    for direction in REQUIRED_DIRECTIONS:
        raw = samples_by_direction[direction]
        if not raw:
            raise ValueError("empty sight-line inventory: " + direction)
        if any(not isinstance(s.get("distance_m"), (int, float)) or
               s["distance_m"] < 0 or not isinstance(s.get("visible"), bool) or
               not s.get("source_ref") for s in raw):
            raise ValueError("invalid or unbound sight-line sample: " + direction)
        ordered = sorted(raw, key=lambda s: s["distance_m"])
        distances = [s["distance_m"] for s in ordered]
        if len(set(distances)) != len(distances):
            raise ValueError("duplicate approach station: " + direction)
        through = [s for s in ordered if s["distance_m"] <= STATUTORY_DISTANCE_M]
        far = [s for s in ordered if s["distance_m"] >= STATUTORY_DISTANCE_M]
        blocked = [s for s in through if not s["visible"]]
        output["directions"][direction] = {
            "sample_count": len(ordered),
            "has_sample_at_or_beyond_500ft": bool(far),
            "nearest_observed_blockage_m": min((s["distance_m"] for s in blocked), default=None),
            "farthest_observed_clear_m": max((s["distance_m"] for s in through if s["visible"]), default=None),
            "source_refs": [s["source_ref"] for s in ordered],
            "interpretation": "virtual_observer_proxy_only",
        }
    return output


def summarize_native_frame(visibility: dict, source_sha256: str,
                           expected_lane_ids: list[int]) -> dict:
    """Retain the pinned nine-body sight proxy and both lane-specific bounds.

    The caller must bind `source_sha256` to the original Native visibility
    record. This function does not replace the retained ray packet or decide a
    legal visibility threshold.
    """
    from traffic_spec_adapter.visibility import sight_distance, CONVENTION

    if (not isinstance(source_sha256, str) or len(source_sha256) != 64 or
            any(ch not in "0123456789abcdef" for ch in source_sha256)):
        raise ValueError("Original visibility source SHA-256 required")
    if (not isinstance(expected_lane_ids, list) or len(expected_lane_ids) != 2 or
            len(set(expected_lane_ids)) != 2 or any(type(x) is not int for x in expected_lane_ids)):
        raise ValueError("Two distinct sourced incoming lane IDs required")
    if (visibility.get("required_lane_ids") != expected_lane_ids or
            visibility.get("probe_distance_m") != STATUTORY_DISTANCE_M or
            visibility.get("eye_height_m") != 1.4 or
            visibility.get("distance_convention") != CONVENTION):
        raise ValueError("Original visibility convention or lane inventory differs")
    value, reason = sight_distance(visibility)
    approaches = visibility.get("approaches", [])
    if len(approaches) != 2 or {a.get("lane_id") for a in approaches} != set(expected_lane_ids):
        raise ValueError("Both sourced incoming approach rays required")
    details = []
    for approach in approaches:
        horizon = approach.get("any_body_sight_horizon", {})
        if horizon.get("bound") == "first_sampled_occlusion":
            bounds = horizon.get("bracket_m")
        elif horizon.get("bound") == "at_least":
            bounds = [horizon.get("distance_m"), None]
        else:
            bounds = None
        details.append({"lane_id": approach["lane_id"], "bound_kind": horizon.get("bound"),
                        "bounds_m": bounds, "clear_at_500ft": approach.get("any_sample_clear_at_probe"),
                        "unknown_reason": approach.get("unknown_reason")})
    return {"source_sha256": source_sha256, "statutory_reference_m": STATUTORY_DISTANCE_M,
            "pinned_proxy_m": value, "pinned_proxy_reason": reason,
            "incoming_approaches": details, "legal_visibility_judgment": None,
            "actual_driver_eye_verified": False}
