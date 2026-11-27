"""Saved-only measurements for the cyclist due-care comparison.

The output keeps the statutory judgment unresolved. A requested bicycle
blueprint and synthetic source rows cannot establish a person riding it.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from scene import fixed_context
from cyclist_response import response_command

ASSIGNMENT = "training__C136495__NRS-484B-270-5a__motor_vehicle_driver"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCES = ("actor-frames.jsonl", "camera-frame-map.jsonl", "response-control.jsonl",
           "classification.json", "collision-events.jsonl")


def _number(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Missing numeric original source: " + label)
    return float(value)


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def finalize(folder: str | Path) -> dict:
    folder = Path(folder)
    binding = json.loads((folder / "rider-binding.json").read_text())
    condition = binding.get("condition")
    suffix = {"early_response": "condition_a", "later_response": "condition_b"}.get(condition)
    if binding.get("format") != "c136495-native-source-manifest-v1" or suffix is None:
        raise ValueError("Wrong exact cyclist source binding")
    if binding.get("case_id") != ASSIGNMENT + "__selected_a21cf01e__" + suffix:
        raise ValueError("Wrong exact cyclist case identity")
    if binding.get("candidate_id") not in ("primary", "fallback1"):
        raise ValueError("Wrong selected construction candidate")
    if binding.get("fixed_context") != fixed_context():
        raise ValueError("Fixed source context differs")
    hashes = binding.get("sha256", {})
    if set(hashes) != set(SOURCES):
        raise ValueError("Missing original source inventory")
    for name in SOURCES:
        source = folder / name
        if not source.is_file():
            raise ValueError("Missing original source: " + name)
        if hashlib.sha256(source.read_bytes()).hexdigest() != hashes[name]:
            raise ValueError("Original source hash differs: " + name)
    classification = json.loads((folder / "classification.json").read_text())
    if classification.get("driver_actor_role") != "motor_vehicle_driver":
        raise ValueError("Missing motor-vehicle driver role source")
    if classification.get("requested_rider_vehicle_type") != "bicycle":
        raise ValueError("Missing requested bicycle blueprint source")
    for field in ("actual_person_riding", "wheel_configuration", "propulsion",
                  "moped_exclusion", "due_care"):
        if classification.get(field) != "unresolved":
            raise ValueError("Unsupported physical or due-care assertion: " + field)
    wheel_radii = classification.get("native_wheel_radii_m")
    if not isinstance(wheel_radii, list) or len(wheel_radii) < 2 or not all(
        0 < _number(radius, "wheel radius") < 1 for radius in wheel_radii
    ):
        raise ValueError("Missing source-shaped native wheel dimensions")
    actors = _rows(folder / "actor-frames.jsonl")
    cameras = _rows(folder / "camera-frame-map.jsonl")
    controls = _rows(folder / "response-control.jsonl")
    events = _rows(folder / "collision-events.jsonl")
    if len(actors) != 600 or len(cameras) != 600 or len(controls) != 600:
        raise ValueError("Missing 600-frame original source")
    first = actors[0].get("native_frame")
    if type(first) is not int:
        raise ValueError("Missing first Native frame")
    event_frames = []
    for event in events:
        frame = event.get("native_frame")
        if type(frame) is not int or not first <= frame < first + 600:
            raise ValueError("Collision event frame outside original source")
        if type(event.get("other_actor_id")) is not int or not event.get("other_actor_type"):
            raise ValueError("Collision event lacks original other-actor identity")
        event_frames.append(frame)
    minimum_gap = math.inf
    minimum_ttc = math.inf
    minimum_accel = math.inf
    near_frames = 0
    prior_speed = None
    prior_xy = None
    prior_bodies = None
    braking_frames = 0
    for index, (row, camera, control) in enumerate(zip(actors, cameras, controls)):
        frame = first + index
        if row.get("native_frame") != frame or camera.get("native_frame") != frame:
            raise ValueError("Original actor/camera frame join differs")
        if control.get("native_frame") != frame or control.get("condition") != condition:
            raise ValueError("Original response control identity differs")
        t = _number(row.get("time_s"), "actor time")
        if abs(t - index / 20) > .051 or abs(
            _number(camera.get("time_s"), "camera time") - t
        ) > .051:
            raise ValueError("Original actor/camera time join differs")
        if abs(_number(control.get("time_s"), "response time") - t) > .051:
            raise ValueError("Original response time join differs")
        expected_command = response_command(
            condition, _number(control.get("source_forward_gap_m"), "response gap"),
            _number(control.get("source_ego_speed_mps"), "response speed"))
        if control.get("command") != expected_command:
            raise ValueError("Original measured-gap response command differs")
        if prior_bodies is not None:
            old_ego, old_rider = prior_bodies
            prior_gap = (old_rider["x_m"] - old_ego["x_m"] -
                         (old_ego["body_length_m"] + old_rider["body_length_m"]) / 2)
            prior_speed_source = math.hypot(old_ego["vx_mps"], old_ego["vy_mps"])
            if (abs(control["source_forward_gap_m"] - prior_gap) > .15 or
                    abs(control["source_ego_speed_mps"] - prior_speed_source) > .15):
                raise ValueError("Response input differs from preceding original actor pose")
        braking_frames += expected_command["brake"] > 0
        camera_frames = camera.get("camera_frames", {})
        if set(camera_frames) != set(CAMERAS) or any(
            camera_frames[name] != frame for name in CAMERAS
        ):
            raise ValueError("Four original cameras missing or unsynchronized")
        bodies = row.get("actors", {})
        if set(bodies) != {"ego", "rider"}:
            raise ValueError("Separate original vehicle and bicycle actors missing")
        ego, rider = bodies["ego"], bodies["rider"]
        if ego.get("actor_id") == rider.get("actor_id") or any(
            type(body.get("actor_id")) is not int for body in (ego, rider)
        ):
            raise ValueError("Original actor identities are not distinct")
        ex, ey, evx, evy = (_number(ego.get(name), "ego " + name)
                            for name in ("x_m", "y_m", "vx_mps", "vy_mps"))
        rx, ry, rvx, rvy = (_number(rider.get(name), "rider " + name)
                            for name in ("x_m", "y_m", "vx_mps", "vy_mps"))
        ego_radius = math.hypot(_number(ego.get("body_length_m"), "ego length"),
                                _number(ego.get("body_width_m"), "ego width")) / 2
        rider_radius = math.hypot(_number(rider.get("body_length_m"), "rider length"),
                                  _number(rider.get("body_width_m"), "rider width")) / 2
        delta = math.hypot(rx - ex, ry - ey)
        gap = delta - ego_radius - rider_radius
        minimum_gap = min(minimum_gap, gap)
        closing = ((rx - ex) * (evx - rvx) + (ry - ey) * (evy - rvy)) / max(delta, .001)
        if gap > 0 and closing > 0:
            minimum_ttc = min(minimum_ttc, gap / closing)
        if abs(rx - ex) < 12:
            near_frames += 1
        speed = math.hypot(evx, evy)
        if prior_speed is not None:
            minimum_accel = min(minimum_accel, (speed - prior_speed) * 20)
            for old, new, velocity in ((prior_xy[0], (ex, ey), (evx, evy)),
                                        (prior_xy[1], (rx, ry), (rvx, rvy))):
                if math.dist(old, new) > math.hypot(*velocity) / 20 + .5:
                    raise ValueError("Original pose and velocity disagree")
        prior_speed = speed
        prior_xy = ((ex, ey), (rx, ry))
        prior_bodies = (ego, rider)
    if near_frames == 0:
        raise ValueError("Original actors never reached interaction window")
    return {"format": "c136495-due-care-measurement-v1",
            "case_id": binding["case_id"], "condition": condition,
            "candidate_id": binding["candidate_id"], "source_sha256": hashes,
            "first_native_frame": first, "frame_count": 600,
            "camera_names": list(CAMERAS), "near_frames": near_frames,
            "minimum_surface_gap_m": round(minimum_gap, 6),
            "minimum_projected_ttc_s": None if minimum_ttc == math.inf else round(minimum_ttc, 6),
            "minimum_longitudinal_acceleration_mps2": round(minimum_accel, 6),
            "collision_sensor_event_count": len(event_frames),
            "requested_braking_frames": braking_frames,
            "person_riding_bicycle_verified": False,
            "due_care_judgment": "unresolved", "legal_verdict_claimed": False,
            "physical_native_verified": False}
