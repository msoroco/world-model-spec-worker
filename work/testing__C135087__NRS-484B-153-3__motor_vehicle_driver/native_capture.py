"""Source-gated original Native door and loading acquisition for C135087.

The reviewed operator supplies actors, four camera callbacks, and an independent
per-frame door/activity observation. A command is never an observation. This
module keeps packet and image outputs in the local attempt, not worker work/.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT = "testing__C135087__NRS-484B-153-3__motor_vehicle_driver"
CASES = ("cargo_active", "cargo_inactive", "passenger_active",
         "passenger_inactive", "opposite_side_control")
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
RATE_HZ = 20
FRAME_COUNT = 900


def _read_hashed(path: Path, expected: str) -> dict:
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("reviewed source hash mismatch")
    return json.loads(raw)


def _finite(value):
    return type(value) in (float, int) and math.isfinite(value)


def _point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2 or not all(map(_finite, value)):
        raise ValueError("original point missing")
    return [float(value[0]), float(value[1])]


def validate_survey(packet: dict, case_id: str) -> dict:
    kind = case_id.removeprefix(ASSIGNMENT + "__")
    if case_id != ASSIGNMENT + "__" + kind or kind not in CASES:
        raise ValueError("unknown exact door case")
    if packet.get("source_kind") != "reviewed_original_native_site" or packet.get("cell_id") != "C135087":
        raise ValueError("reviewed C135087 Native site required")
    if not isinstance(packet.get("map_sha256"), str) or len(packet["map_sha256"]) != 64:
        raise ValueError("original loaded map hash missing")
    if packet.get("layout") != "narrow_road" or packet.get("maneuver") != "load_unload":
        raise ValueError("reviewed narrow-road loading identity mismatch")
    if packet.get("loading_position_supported") is not True:
        raise ValueError("supported loading position not reviewed")
    for name in ("road_width_m", "selected_vehicle_width_m", "selected_vehicle_length_m"):
        if not _finite(packet.get(name)) or packet[name] <= 0:
            raise ValueError("reviewed geometry missing: " + name)
    _point(packet.get("selected_vehicle_center_xy_m"))
    _point(packet.get("passing_start_xy_m"))
    _point(packet.get("passing_end_xy_m"))
    if packet.get("selected_vehicle_heading_deg") != 0:
        raise ValueError("survey must prove +x selected-vehicle heading for side interpretation")
    center_y = packet["selected_vehicle_center_xy_m"][1]
    passing_y = packet["passing_start_xy_m"][1]
    if abs(passing_y - center_y) <= (packet["selected_vehicle_width_m"] / 2):
        raise ValueError("passing route has no distinct lateral body lane")
    if (packet["passing_end_xy_m"][1] - center_y) * (passing_y - center_y) <= 0:
        raise ValueError("passing route crosses selected vehicle centerline")
    if not packet.get("loading_position_source_sha256") or not packet.get("passing_route_source_sha256"):
        raise ValueError("reviewed site and passing route citations required")
    if not packet.get("selected_vehicle_blueprint") or not packet.get("passing_vehicle_blueprint"):
        raise ValueError("reviewed vehicle blueprints required")
    if not packet.get("cargo_actor_blueprint") or not packet.get("passenger_actor_blueprint"):
        raise ValueError("reviewed loading actor blueprints required")
    return packet


def _actor_id(actor) -> str:
    value = getattr(actor, "id", None)
    if type(value) not in (int, str) or not str(value):
        raise ValueError("original actor ID missing")
    return str(value)


def _save_packet(output: Path, name: str, value: dict) -> dict:
    path = output / (name + ".json")
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path.write_bytes(raw)
    return {"path": path.name, "sha256": hashlib.sha256(raw).hexdigest()}


def capture(world, *, case_id: str, survey_path: Path, survey_sha256: str,
            output: Path, map_reader, actor_factory, door_controller,
            loading_controller, original_observer, camera_factory):
    """Capture one exact case from a reviewed source-bound Native operator.

    Operator callbacks are mandatory. `original_observer` must read door
    articulation, loading actor body/motion and passing body after each tick.
    CARLA world settings and owned actors/sensors are restored in `finally`.
    """
    packet = validate_survey(_read_hashed(survey_path, survey_sha256), case_id)
    if not all(callable(fn) for fn in (map_reader, actor_factory, door_controller,
                                       loading_controller, original_observer, camera_factory)):
        raise ValueError("reviewed Native operator callbacks missing")
    def map_hash():
        data = map_reader(world)
        if type(data) is not bytes or not data:
            raise ValueError("original loaded map bytes missing")
        return hashlib.sha256(data).hexdigest()
    if map_hash() != packet["map_sha256"]:
        raise ValueError("loaded map differs from reviewed source")
    output = Path(output)
    if (output / "inventory.json").exists():
        raise ValueError("original attempt already exists")
    output.mkdir(parents=True, exist_ok=True)
    original_settings = copy.copy(world.get_settings())
    settings = copy.copy(original_settings)
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 1 / RATE_HZ
    owned = []
    try:
        world.apply_settings(settings)
        readback = world.get_settings()
        if readback.synchronous_mode is not True or abs(readback.fixed_delta_seconds - .05) > 1e-9:
            raise ValueError("Native 20 Hz clock readback failed")
        selected = actor_factory(world, "selected_vehicle", packet, None)
        passing = actor_factory(world, "passing_vehicle", packet, None)
        load_kind = "passenger" if case_id.endswith("passenger_active") or case_id.endswith("passenger_inactive") else "cargo"
        loading_actor = actor_factory(world, load_kind, packet, None)
        owned.extend((selected, passing, loading_actor))
        if any(actor is None or not getattr(actor, "is_alive", False) for actor in owned):
            raise ValueError("original Native actor spawn failed")
        if len({_actor_id(actor) for actor in owned}) != 3:
            raise ValueError("original participant identity collision")
        cameras = camera_factory(world, selected, VIEWS, packet)
        if not isinstance(cameras, dict) or set(cameras) != set(VIEWS):
            raise ValueError("four original cameras missing")
        if any(not callable(cameras[name]) for name in VIEWS):
            raise ValueError("original camera callbacks missing")
        traffic_side = "left" if packet["passing_start_xy_m"][1] > packet["selected_vehicle_center_xy_m"][1] else "right"
        side = ("right" if traffic_side == "left" else "left") if case_id.endswith("opposite_side_control") else traffic_side
        active_case = not case_id.endswith("inactive")
        frame_rows, door_rows, activity_rows, passing_rows = [], [], [], []
        first_time = None
        last_frame = None
        for index in range(FRAME_COUNT):
            if index == 120 and not door_controller(selected, "open", side):
                raise ValueError("Native door controller refused open")
            if index == 720 and not door_controller(selected, "close", side):
                raise ValueError("Native door controller refused close")
            active_command = 120 <= index < (720 if active_case else 360)
            if not loading_controller(loading_actor, selected, load_kind, active_command, index):
                raise ValueError("Native loading controller refused")
            frame = world.tick()
            snapshot = world.get_snapshot()
            sim_time = float(snapshot.timestamp.elapsed_seconds)
            if type(frame) is not int or frame != snapshot.frame or (last_frame is not None and frame != last_frame + 1):
                raise ValueError("Native frame identity gap")
            if first_time is None:
                first_time = sim_time
            if abs(sim_time - first_time - index * .05) > .005:
                raise ValueError("Native 20 Hz clock drift")
            last_frame = frame
            observed = original_observer(frame, selected, passing, loading_actor)
            if not isinstance(observed, dict) or observed.get("source_frame_id") != frame:
                raise ValueError("independent original observer frame missing")
            if observed.get("selected_vehicle_id") != _actor_id(selected) or observed.get("passing_vehicle_id") != _actor_id(passing) or observed.get("loading_actor_id") != _actor_id(loading_actor):
                raise ValueError("original observer participant identity mismatch")
            observed_selected = _point(observed.get("selected_vehicle_center_xy_m"))
            if any(abs(a - b) > .1 for a, b in zip(observed_selected, packet["selected_vehicle_center_xy_m"])):
                raise ValueError("selected vehicle left reviewed loading position")
            if observed.get("selected_vehicle_heading_deg") is None or abs(observed["selected_vehicle_heading_deg"]) > 2:
                raise ValueError("selected vehicle original heading differs from survey")
            door_angle = observed.get("door_angle_deg")
            if not _finite(door_angle) or not 0 <= door_angle <= 110:
                raise ValueError("original door articulation readback missing")
            observed_side = observed.get("door_side")
            if observed_side != side:
                raise ValueError("original opened door side readback mismatch")
            if observed.get("door_observation_source") != "native_articulation_readback":
                raise ValueError("door command is not an articulation observation")
            open_readback = door_angle >= 15
            if index < 120 or index >= 720:
                if open_readback:
                    raise ValueError("door did not close in original observation")
            elif not open_readback:
                raise ValueError("door did not open in original observation")
            load_body = observed.get("loading_actor_body_xy_m")
            if not isinstance(load_body, list) or len(load_body) < 4:
                raise ValueError("original loading actor body absent")
            for point in load_body:
                _point(point)
            motion = observed.get("loading_actor_speed_mps")
            if not _finite(motion) or motion < 0:
                raise ValueError("loading actor original motion absent")
            if observed.get("loading_observation_source") != "native_actor_body_motion":
                raise ValueError("loading command is not an activity observation")
            active_readback = bool(observed.get("loading_contact_with_vehicle")) and motion > .05
            if 120 <= index < 720 and active_readback != active_command:
                raise ValueError("original loading activity differs from controlled phase")
            passing_body = observed.get("passing_vehicle_body_xy_m")
            if not isinstance(passing_body, list) or len(passing_body) < 4:
                raise ValueError("original passing body absent")
            for point in passing_body:
                _point(point)
            cx, cy = _point(observed.get("passing_vehicle_center_xy_m"))
            if (cy - observed_selected[1]) * (packet["passing_start_xy_m"][1] - packet["selected_vehicle_center_xy_m"][1]) <= 0:
                raise ValueError("observed passing vehicle on wrong traffic side")
            width, length = observed.get("passing_vehicle_width_m"), observed.get("passing_vehicle_length_m")
            if not _finite(width) or not _finite(length) or width <= 0 or length <= 0:
                raise ValueError("original passing body dimensions missing")
            for name in VIEWS:
                image = cameras[name](frame)
                if type(image) is not bytes or not image:
                    raise ValueError("original synchronized camera frame absent: " + name)
                view_dir = output / "cameras" / name
                view_dir.mkdir(parents=True, exist_ok=True)
                (view_dir / f"{frame:06d}.png").write_bytes(image)
            time_s = round(index / RATE_HZ, 5)
            stamp = {"frame": frame, "time_s": time_s}
            frame_rows.append(stamp)
            door_rows.append(dict(stamp, open=open_readback, side=side, angle_deg=float(door_angle)))
            activity_rows.append(dict(stamp, kind=load_kind, active=active_readback,
                                      loading_actor_id=_actor_id(loading_actor),
                                      speed_mps=float(motion), body_xy_m=load_body))
            passing_rows.append(dict(stamp, vehicle_id=_actor_id(passing), center_x_m=cx,
                                     center_y_m=cy, width_m=float(width), length_m=float(length),
                                     body_xy_m=passing_body))
        geometry = {"source_kind": "original_native_geometry", "selected_vehicle_id": _actor_id(selected),
                    "passing_vehicle_id": _actor_id(passing), "loading_position_supported": True,
                    "road_width_m": packet["road_width_m"],
                    "selected_vehicle_width_m": packet["selected_vehicle_width_m"],
                    "selected_vehicle_length_m": packet["selected_vehicle_length_m"],
                    "selected_vehicle_center_x_m": packet["selected_vehicle_center_xy_m"][0],
                    "selected_vehicle_center_y_m": packet["selected_vehicle_center_xy_m"][1],
                    "site_survey_sha256": survey_sha256,
                    "map_sha256": packet["map_sha256"]}
        sources = {
            "frame_map": _save_packet(output, "frame_map", {"case_id": case_id, "source_kind": "original_native", "frames": frame_rows}),
            "door": _save_packet(output, "door", {"case_id": case_id, "source_kind": "original_native", "vehicle_id": _actor_id(selected), "samples": door_rows}),
            "activity": _save_packet(output, "activity", {"case_id": case_id, "source_kind": "original_native", "vehicle_id": _actor_id(selected), "samples": activity_rows}),
            "passing_vehicle": _save_packet(output, "passing_vehicle", {"case_id": case_id, "source_kind": "original_native", "samples": passing_rows}),
            "geometry": _save_packet(output, "geometry", geometry)}
        inventory = {"case_id": case_id, "source_kind": "original_native", "sources": sources,
                     "camera_views": list(VIEWS), "frame_count": FRAME_COUNT,
                     "survey_sha256": survey_sha256}
        _save_packet(output, "inventory", inventory)
        if map_hash() != packet["map_sha256"]:
            raise ValueError("loaded map changed during Native acquisition")
        return inventory
    finally:
        for actor in reversed(owned):
            if actor is not None:
                try:
                    if hasattr(actor, "stop"):
                        actor.stop()
                finally:
                    actor.destroy()
        world.apply_settings(original_settings)
        restored = world.get_settings()
        if restored.synchronous_mode != original_settings.synchronous_mode or restored.fixed_delta_seconds != original_settings.fixed_delta_seconds:
            raise ValueError("Native clock restoration readback failed")
