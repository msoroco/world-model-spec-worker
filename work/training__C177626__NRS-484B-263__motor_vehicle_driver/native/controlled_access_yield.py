"""Source-shaped controlled-access yield controller and measurements.

The controller thresholds are engineering settings for diagnostics. They are
not definitions of immediate hazard or reasonable safety under NRS 484B.263.
"""

from __future__ import annotations

from math import hypot, isfinite

FRAME_COUNT = 600
FRAME_RATE = 20
POLICY_GAP_S = {"earlier_yield": 5.0, "later_yield": 2.5}


def control_request(policy: str, arrival_gap_s: float | None) -> dict:
    if policy not in POLICY_GAP_S:
        raise ValueError("unknown yield comparison policy")
    if arrival_gap_s is not None and (not isfinite(arrival_gap_s) or arrival_gap_s < 0):
        raise ValueError("invalid measured arrival gap")
    if arrival_gap_s is not None and arrival_gap_s < POLICY_GAP_S[policy]:
        return {"throttle": 0.0, "brake": 0.65, "yield_request": True}
    return {"throttle": 0.3, "brake": 0.0, "yield_request": False}


def measure_trace(rows: list[dict], network: dict) -> dict:
    if len(rows) != FRAME_COUNT:
        raise ValueError("source trace must contain 600 frames")
    if network.get("route_kind") not in ("entry", "exit"):
        raise ValueError("controlled-access entry or exit route required")
    required = ("highway_source", "controlled_access_source", "ramp_lane_id", "highway_lane_id", "conflict_point_source")
    if not all(network.get(k) for k in required) or network["ramp_lane_id"] == network["highway_lane_id"]:
        raise ValueError("sourced distinct highway and ramp lanes required")
    min_gap = float("inf")
    min_arrival_gap = float("inf")
    max_through_braking = 0.0
    through_presence = 0
    yield_frames = 0
    previous_through_speed = None
    for i, row in enumerate(rows):
        if row.get("frame") != i or abs(row.get("time_s", -1) - i / FRAME_RATE) > 1e-6:
            raise ValueError("source frame identity or 20 Hz join failed")
        keys = ("ego_x_m", "ego_y_m", "ego_vx_mps", "ego_vy_mps", "ego_radius_m",
                "through_x_m", "through_y_m", "through_vx_mps", "through_vy_mps", "through_radius_m",
                "ego_distance_to_conflict_m", "through_distance_to_conflict_m")
        try:
            v = [float(row[k]) for k in keys]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("raw actor geometry and conflict distances required") from exc
        if not all(isfinite(x) for x in v) or min(v[4], v[9]) <= 0 or min(v[10], v[11]) < 0:
            raise ValueError("invalid raw actor geometry and conflict distances")
        if type(row.get("through_on_highway")) is not bool or type(row.get("ego_yielding")) is not bool:
            raise ValueError("highway-presence and yielding source required")
        through_presence += int(row["through_on_highway"])
        yield_frames += int(row["ego_yielding"])
        ex, ey, evx, evy, er, tx, ty, tvx, tvy, tr, ed, td = v
        min_gap = min(min_gap, hypot(tx - ex, ty - ey) - er - tr)
        ego_speed, through_speed = hypot(evx, evy), hypot(tvx, tvy)
        if ego_speed > 0 and through_speed > 0 and row["through_on_highway"]:
            min_arrival_gap = min(min_arrival_gap, abs(ed / ego_speed - td / through_speed))
        if previous_through_speed is not None:
            max_through_braking = max(max_through_braking, (previous_through_speed - through_speed) * FRAME_RATE)
        previous_through_speed = through_speed
    if through_presence == 0:
        raise ValueError("approaching highway traffic source required")
    return {
        "frames": FRAME_COUNT,
        "duration_s": FRAME_COUNT / FRAME_RATE,
        "route_kind": network["route_kind"],
        "minimum_surface_gap_m": min_gap,
        "minimum_projected_arrival_gap_s": None if min_arrival_gap == float("inf") else min_arrival_gap,
        "maximum_through_deceleration_mps2": max_through_braking,
        "observed_yield_frames": yield_frames,
        "legal_immediate_hazard_conclusion": None,
        "legal_reasonable_safety_conclusion": None,
        "source_kind": "unverified_raw_actor_and_network_fields",
    }
