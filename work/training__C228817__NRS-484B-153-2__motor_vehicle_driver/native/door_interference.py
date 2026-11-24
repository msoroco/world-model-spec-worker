"""Source-shaped traffic-side door and passing-vehicle measurements.

Door motion, boarding and traffic response are measured separately. Their
combination does not itself decide statutory interference under NRS 484B.153(2).
"""

from __future__ import annotations

from math import cos, hypot, isfinite, sin

FRAME_COUNT = 600
FRAME_RATE = 20
OPEN_GAP_S = {"earlier_open": 3.0, "later_open": 6.0}


def door_request(mode: str, passing_arrival_gap_s: float | None) -> bool:
    if mode not in OPEN_GAP_S:
        raise ValueError("unknown door comparison mode")
    if passing_arrival_gap_s is None:
        return True
    if not isfinite(passing_arrival_gap_s) or passing_arrival_gap_s < 0:
        raise ValueError("invalid passing arrival gap")
    return passing_arrival_gap_s >= OPEN_GAP_S[mode]


def _segment_gap(px, py, hx, hy, tx, ty, radius):
    ux, uy = tx-hx, ty-hy
    d = ux*ux+uy*uy
    if d <= 0:
        raise ValueError("degenerate door sweep")
    t = max(0.0, min(1.0, ((px-hx)*ux+(py-hy)*uy)/d))
    return hypot(px-hx-t*ux, py-hy-t*uy)-radius


def measure_trace(rows: list[dict], scene: dict) -> dict:
    if len(rows) != FRAME_COUNT:
        raise ValueError("source trace must contain 600 frames")
    required = ("parked_vehicle_source", "traffic_side_source", "passing_lane_source", "door_hinge_source", "boarding_person_source")
    if not all(scene.get(k) for k in required):
        raise ValueError("stopped vehicle, traffic side, lane, door and person provenance required")
    if scene.get("door_side") != "closest_to_passing_traffic":
        raise ValueError("traffic-side door required")
    min_swept_gap = float("inf")
    open_frames = 0
    moving_traffic_frames = 0
    person_transfer_frames = 0
    max_passing_deceleration = 0.0
    last_speed = None
    for i, row in enumerate(rows):
        if row.get("frame") != i or abs(row.get("time_s", -1) - i / FRAME_RATE) > 1e-6:
            raise ValueError("source frame identity or 20 Hz join failed")
        keys = ("door_hinge_x_m", "door_hinge_y_m", "door_length_m", "door_angle_rad",
                "passing_x_m", "passing_y_m", "passing_radius_m", "passing_vx_mps", "passing_vy_mps")
        try:
            hx, hy, length, angle, px, py, radius, vx, vy = [float(row[k]) for k in keys]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("raw door geometry and passing traffic motion required") from exc
        if not all(isfinite(v) for v in (hx, hy, length, angle, px, py, radius, vx, vy)) or length <= 0 or radius <= 0:
            raise ValueError("invalid raw door or passing traffic geometry")
        for key in ("vehicle_stopped", "door_open", "person_boarding_or_alighting", "passing_vehicle_in_lane"):
            if type(row.get(key)) is not bool:
                raise ValueError("stop, door, person and passing-lane sources required")
        if not row["vehicle_stopped"]:
            raise ValueError("loading vehicle must be stopped during source trace")
        speed = hypot(vx, vy)
        moving_traffic_frames += int(row["passing_vehicle_in_lane"] and speed > 0.05)
        open_frames += int(row["door_open"])
        person_transfer_frames += int(row["person_boarding_or_alighting"])
        if row["door_open"] and row["passing_vehicle_in_lane"]:
            tip_x, tip_y = hx+length*cos(angle), hy+length*sin(angle)
            min_swept_gap = min(min_swept_gap, _segment_gap(px, py, hx, hy, tip_x, tip_y, radius))
        if last_speed is not None:
            max_passing_deceleration = max(max_passing_deceleration, (last_speed-speed)*FRAME_RATE)
        last_speed = speed
    if moving_traffic_frames == 0:
        raise ValueError("moving vehicular traffic required")
    return {
        "frames": FRAME_COUNT,
        "duration_s": FRAME_COUNT / FRAME_RATE,
        "door_open_frames": open_frames,
        "person_transfer_frames": person_transfer_frames,
        "moving_passing_traffic_frames": moving_traffic_frames,
        "minimum_door_segment_to_vehicle_surface_gap_m": None if min_swept_gap == float("inf") else min_swept_gap,
        "maximum_passing_deceleration_mps2": max_passing_deceleration,
        "legal_interference_conclusion": None,
        "source_kind": "unverified_raw_door_person_and_vehicle_fields",
    }
