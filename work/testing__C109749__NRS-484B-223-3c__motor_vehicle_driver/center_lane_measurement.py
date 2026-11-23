"""Source-bound geometry for NRS 484B.223(3)(c) preparation.

Inputs are original Native frame samples. This module does not decide legality.
"""

from math import hypot, isfinite

FEET_PER_METRE = 3.280839895013123
LIMIT_FEET = 50.0


def _point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("body centre requires two planar coordinates")
    x, y = float(value[0]), float(value[1])
    if not isfinite(x) or not isfinite(y):
        raise ValueError("non-finite body centre")
    return x, y


def measure_center_lane_distance(packet):
    """Integrate actual body-centre travel after turn completion until merge.

    Lane membership and event markers must come from Native lane/body geometry.
    A missing merge is censored and never assigned a numeric legal outcome.
    """
    for field in ("source", "highway_context_source", "lane_design_source", "samples"):
        if not packet.get(field):
            raise ValueError("missing original source: " + field)
    if packet.get("lane_design") != "single_shared_bidirectional_center_turn_only":
        raise ValueError("unverified shared center turn lane design")
    samples = packet["samples"]
    if len(samples) < 3:
        raise ValueError("insufficient original samples")
    frames = [row.get("frame") for row in samples]
    if any(type(frame) is not int for frame in frames) or any(b != a + 1 for a, b in zip(frames, frames[1:])):
        raise ValueError("Native frames must be contiguous")
    points = [_point(row.get("body_centre_xy_m")) for row in samples]
    turns = [i for i, row in enumerate(samples) if row.get("left_turn_onto_highway_complete") is True]
    if len(turns) != 1:
        raise ValueError("exactly one original turn completion event required")
    start = turns[0]
    if samples[start].get("lane") != "shared_center_turn":
        raise ValueError("turn did not finish in shared center lane")
    merge_indices = [i for i in range(start + 1, len(samples)) if samples[i].get("merged_into_through_lane") is True]
    end = merge_indices[0] if merge_indices else len(samples) - 1
    for row in samples[start:end]:
        if row.get("lane") != "shared_center_turn":
            raise ValueError("untracked center lane exit before merge")
    if merge_indices and samples[end].get("lane") != "receiving_through":
        raise ValueError("merge marker lacks receiving through lane")
    distance_m = sum(hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1]) for i in range(start + 1, end + 1))
    return {
        "source": packet["source"],
        "turn_frame": frames[start],
        "merge_frame": frames[end] if merge_indices else None,
        "distance_m": distance_m,
        "distance_ft": distance_m * FEET_PER_METRE,
        "boundary_ft": LIMIT_FEET,
        "merge_observed": bool(merge_indices),
        "censored": not bool(merge_indices),
        "measurement_convention": "Original body-centre XY path from first post-turn sample through first through-lane merge sample; retain raw frame history for reviewer convention check.",
    }
