"""Measured saved body, passenger and sign evidence without a legal verdict."""

from datetime import datetime
import math
from zoneinfo import ZoneInfo

from .loading_scene import FRAMES, RATE_HZ


def sign_effective(timestamp, sign):
    if not sign.get("sign_id") or not sign.get("map_readback_sha256"):
        raise ValueError("original sign source missing")
    start, end = sign.get("sign_text_hours", [])
    def minutes(value):
        hour, minute = map(int, value.split(":"))
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError("invalid original sign hours")
        return 60 * hour + minute
    a, b = minutes(start), minutes(end)
    if a == b:
        raise ValueError("ambiguous original sign hours")
    instant = datetime.fromisoformat(timestamp)
    if instant.tzinfo is None:
        raise ValueError("original civil timestamp lacks offset")
    local = instant.astimezone(ZoneInfo(sign["time_zone"]))
    clock = local.hour * 60 + local.minute
    return a <= clock < b if a < b else clock >= a or clock < b


def measure(context, sign, motion, ego_bodies, passenger_bodies, frames, trace):
    if not all(len(rows) == FRAMES for rows in
               (motion, ego_bodies, passenger_bodies, frames, trace)):
        raise ValueError("original 600-frame loading source join incomplete")
    if context.get("regulatory_authority_confirmed") is not False:
        raise ValueError("unsupported original regulatory authority claim")
    if context.get("actual_passenger_transfer_confirmed") is not False:
        raise ValueError("unsupported original passenger-transfer claim")
    zone_start, zone_end = -25, -1
    halted_frames = []
    zone_frames = []
    passenger_near_door_frames = []
    effective_frames = []
    for i, (row, body, passenger, frame, core) in enumerate(
            zip(motion, ego_bodies, passenger_bodies, frames, trace)):
        native = row.get("native_frame")
        if (row.get("video_frame") != i or frame.get("video_frame") != i or
                frame.get("native_frame") != native or core.get("frame") != native or
                body.get("native_frame") != native or passenger.get("native_frame") != native or
                body.get("actor_id") != row.get("ego_actor_id") or
                passenger.get("actor_id") != row.get("passenger_actor_id") or
                abs(row.get("time_s", -1) - i / RATE_HZ) > .005 or
                abs(frame.get("time_s", -2) - row.get("time_s", -3)) > 1e-6 or
                abs(core.get("time_s", -4) - row.get("time_s", -5)) > 1e-6):
            raise ValueError("original frame, actor or Core time join differs")
        if row.get("occupant_count_observed") is not False or row.get("actual_door_state_observed") is not False:
            raise ValueError("unreviewed occupant or door state was asserted")
        if len(body.get("body_vertices_m", [])) < 4 or len(passenger.get("body_vertices_m", [])) < 4:
            raise ValueError("original full body vertices missing")
        xs = [point[0] for point in body["body_vertices_m"]]
        if abs((min(xs) + max(xs)) / 2 - row["vehicle_center_m"][0]) > .05:
            raise ValueError("original vehicle body and motion differ")
        passenger_xyz = row.get("passenger_center_m", [])
        if len(passenger_xyz) != 3 or any(not math.isfinite(value) for value in passenger_xyz):
            raise ValueError("original passenger position missing")
        if not isinstance(row.get("vehicle_speed_mps"), (int, float)) or row["vehicle_speed_mps"] < 0:
            raise ValueError("original vehicle speed missing")
        in_zone = min(xs) >= zone_start and max(xs) <= zone_end
        halted = row["vehicle_speed_mps"] <= .05
        door_y = row["vehicle_center_m"][1] - 1.5
        near_door = abs(passenger_xyz[0] - row["vehicle_center_m"][0]) <= 2.5 and abs(passenger_xyz[1] - door_y) <= 1.0
        halted_frames.append(halted)
        zone_frames.append(in_zone)
        passenger_near_door_frames.append(near_door)
        effective_frames.append(sign_effective(row["civil_timestamp"], sign))
    return {"frames": FRAMES, "duration_s": FRAMES / RATE_HZ,
            "halted_in_marked_segment_frames": sum(h and z for h, z in zip(halted_frames, zone_frames)),
            "effective_sign_hours_frames": sum(effective_frames),
            "door_open_request_frames": sum(bool(row["door_open_request_active"]) for row in motion),
            "passenger_near_door_frames": sum(passenger_near_door_frames),
            "observed_passenger_doorway_transfer": "unconfirmed_pending_video_review",
            "actual_door_state": "unconfirmed_pending_video_review",
            "occupant_count": "unobserved_pending_original_source",
            "zone_regulatory_authority": "unverified_original_source",
            "expeditiousness": "unassessed_original_judgment",
            "motion_tolerance_note": "0.05 m/s is an engineering rest classifier, not a legal grace period"}
