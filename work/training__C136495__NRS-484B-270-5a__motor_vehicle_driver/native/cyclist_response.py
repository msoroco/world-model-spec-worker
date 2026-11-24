"""CPU-verifiable controller and raw-trace measurements for NRS 484B.270(5)(a).

The numeric response distances are engineering settings for two diagnostic
trajectories. They do not define due care or a legal clearance threshold.
"""

from __future__ import annotations

from math import hypot, isfinite

FRAME_COUNT = 600
FRAME_RATE = 20
MODES = {"early_response": 25.0, "later_response": 12.0}


def response_command(mode: str, forward_gap_m: float, speed_mps: float) -> dict:
    """Choose a longitudinal control request from measured relative position."""
    if mode not in MODES:
        raise ValueError("unrecognized comparison control mode")
    if not all(isfinite(v) for v in (forward_gap_m, speed_mps)) or speed_mps < 0:
        raise ValueError("invalid source distance or speed")
    if forward_gap_m <= MODES[mode]:
        return {"throttle": 0.0, "brake": min(1.0, max(0.25, speed_mps / 12.0))}
    return {"throttle": 0.35, "brake": 0.0}


def measure_trace(rows: list[dict], rider_provenance: dict) -> dict:
    """Measure geometry and response from retained raw actor samples.

    Each row contains synchronized actor centres, velocity vectors, bounding
    radii, and a collision sensor flag. A position-only fixture cannot claim
    an actual bicycle, so explicit physical identity provenance is required.
    """
    if len(rows) != FRAME_COUNT:
        raise ValueError("source trace must contain 600 frames")
    required_identity = ("rider_actor_id", "bicycle_actor_id", "wheel_evidence", "propulsion_evidence", "moped_exclusion_evidence")
    if not all(rider_provenance.get(k) for k in required_identity):
        raise ValueError("rider and bicycle physical identity provenance required")
    if rider_provenance["rider_actor_id"] == rider_provenance["bicycle_actor_id"]:
        raise ValueError("rider and bicycle identities must be distinct")
    minimum_gap = float("inf")
    minimum_ttc = float("inf")
    minimum_accel = float("inf")
    contacts = 0
    previous_speed = None
    previous_motion = None
    for i, row in enumerate(rows):
        if row.get("frame") != i or abs(row.get("time_s", -1) - i / FRAME_RATE) > 1e-6:
            raise ValueError("source frame identity or 20 Hz join failed")
        fields = ("ego_x_m", "ego_y_m", "ego_vx_mps", "ego_vy_mps", "ego_radius_m",
                  "rider_x_m", "rider_y_m", "rider_vx_mps", "rider_vy_mps", "rider_radius_m",
                  "bicycle_x_m", "bicycle_y_m", "bicycle_vx_mps", "bicycle_vy_mps")
        try:
            values = [float(row[k]) for k in fields]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("missing raw actor geometry or velocity") from exc
        if not all(isfinite(v) for v in values) or values[4] <= 0 or values[9] <= 0:
            raise ValueError("invalid raw actor geometry or velocity")
        ex, ey, evx, evy, er, rx, ry, rvx, rvy, rr, bx, by, bvx, bvy = values
        if hypot(rx - bx, ry - by) > 1.5 or hypot(rvx - bvx, rvy - bvy) > 0.5:
            raise ValueError("Rider and bicycle sampled motion are not associated")
        current_motion = ((ex, ey, evx, evy), (rx, ry, rvx, rvy), (bx, by, bvx, bvy))
        if previous_motion is not None:
            for old, new in zip(previous_motion, current_motion):
                expected_x = (old[2] + new[2]) / (2 * FRAME_RATE)
                expected_y = (old[3] + new[3]) / (2 * FRAME_RATE)
                if hypot(new[0] - old[0] - expected_x, new[1] - old[1] - expected_y) > 0.15:
                    raise ValueError("Actor pose motion differs from sampled velocity")
        previous_motion = current_motion
        dx, dy = rx - ex, ry - ey
        gap = hypot(dx, dy) - er - rr
        minimum_gap = min(minimum_gap, gap)
        closing = -((dx * (rvx - evx) + dy * (rvy - evy)) / hypot(dx, dy)) if hypot(dx, dy) > 0 else 0.0
        if gap > 0 and closing > 0:
            minimum_ttc = min(minimum_ttc, gap / closing)
        speed = hypot(evx, evy)
        if previous_speed is not None:
            minimum_accel = min(minimum_accel, (speed - previous_speed) * FRAME_RATE)
        previous_speed = speed
        if type(row.get("collision_sensor_contact")) is not bool:
            raise ValueError("collision sensor contact source required")
        contacts += int(row["collision_sensor_contact"])
    return {
        "frames": FRAME_COUNT,
        "duration_s": FRAME_COUNT / FRAME_RATE,
        "minimum_surface_gap_m": minimum_gap,
        "minimum_projected_ttc_s": None if minimum_ttc == float("inf") else minimum_ttc,
        "minimum_longitudinal_acceleration_mps2": minimum_accel,
        "contact_frames": contacts,
        "legal_due_care_conclusion": None,
        "source_kind": "unverified_raw_actor_fields",
    }
