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
