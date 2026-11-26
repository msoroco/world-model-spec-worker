"""Reviewed-map Native acquisition for nine C240647 right-turn controls.

The local operator supplies a CARLA world and source readers. This module
requires original readback on every tick and writes packets only to a local
attempt directory. Route commands are never treated as observed lane use.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = "testing__C240647__LVMC-11-43-010-C2__motor_vehicle_driver"
CASES = {row["case_id"]: row for row in json.loads((HERE / "case-plan.json").read_text())["cases"]}
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
RATE_HZ = 20
FRAME_COUNT = 900


def _module(name):
    spec = importlib.util.spec_from_file_location("c240647_" + name, HERE / (name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def _read_review(path, sha256):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError("reviewed survey hash mismatch")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("reviewed survey object missing")
    return value


def _save(output, name, value):
    path = output / (name + ".json")
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path.write_bytes(raw)
    return {"path": path.name, "sha256": hashlib.sha256(raw).hexdigest()}


def _actor_id(actor):
    value = getattr(actor, "id", None)
    if type(value) not in (int, str) or not str(value):
        raise ValueError("Native operator actor identity missing")
    return str(value)


def _validate_review(review, case):
    case_id = case["case_id"]
    if review.get("source_kind") != "reviewed_original_native_roundabout":
        raise ValueError("reviewed Native roundabout survey required")
    if review.get("assignment_id") != ASSIGNMENT or review.get("cell_id") != "C240647":
        raise ValueError("reviewed assignment and cell mismatch")
    if review.get("jurisdiction") != "Las Vegas, Nevada":
        raise ValueError("roundabout jurisdiction review missing")
    intent = review.get("independent_operator_intent", {})
    if intent.get("case_id") != case_id or intent.get("requested_exit_role") != case["operator_intent_request"] or not intent.get("source_sha256"):
        raise ValueError("independent source-bound operator intention missing")
    if review.get("entry_id") is None or review.get("exit_id") is None:
        raise ValueError("reviewed entry and exit identities missing")
    if review.get("vehicle_blueprint") is None:
        raise ValueError("reviewed vehicle blueprint missing")
    for name in ("map_sha256", "controller_sha256", "weather_sha256", "camera_plan_sha256"):
        if not isinstance(review.get(name), str) or len(review[name]) != 64:
            raise ValueError("reviewed source hash missing: " + name)
    if review.get("case_ids") != list(CASES):
        raise ValueError("reviewed exact case IDs missing")
    if case_id not in CASES:
        raise ValueError("unknown exact right-lane case")


def capture(world, *, case, survey_path, survey_sha256, output, operator, throttle=0.35):
    """Run a complete source-gated, four-view Native capture and restore world.

    The operator implements map_bytes, readback_map, spawn_vehicle,
    actor_state, apply_control, observe, and cameras. `observe` reads the
    original actor's map lane/section and heading after each world tick.
    `cameras` returns four frame-indexed PNG callbacks and owned sensors.
    """
    case_id = case["case_id"]
    if case_id not in CASES or case != CASES[case_id]:
        raise ValueError("unknown exact right-lane case")
    review = _read_review(survey_path, survey_sha256)
    _validate_review(review, case)
    if hashlib.sha256((HERE / "runner.py").read_bytes()).hexdigest() != review["controller_sha256"]:
        raise ValueError("reviewed route controller source hash mismatch")
    for name in ("map_bytes", "readback_map", "spawn_vehicle", "actor_state",
                 "apply_control", "observe", "cameras"):
        if not callable(getattr(operator, name, None)):
            raise ValueError("Native operator callback missing: " + name)
    map_bytes = operator.map_bytes(world)
    if type(map_bytes) is not bytes or hashlib.sha256(map_bytes).hexdigest() != review["map_sha256"]:
        raise ValueError("loaded map differs from reviewed OpenDRIVE source")
    map_packet = operator.readback_map(world)
    if map_packet.get("map_sha256") != review["map_sha256"]:
        raise ValueError("Native map readback hash differs from survey")
    if map_packet.get("jurisdiction") != review["jurisdiction"]:
        raise ValueError("Native map jurisdiction differs from survey")
    route = _module("roundabout")
    topology = route.verify_topology(map_packet, case)
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("original attempt directory already populated")
    output.mkdir(parents=True, exist_ok=True)
    before = copy.copy(world.get_settings())
    settings = copy.copy(before)
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 1 / RATE_HZ
    vehicle = None
    sensors = []
    try:
        world.apply_settings(settings)
        actual = world.get_settings()
        if actual.synchronous_mode is not True or abs(actual.fixed_delta_seconds - .05) > 1e-9:
            raise ValueError("Native 20 Hz settings readback failed")
        class Adapter:
            def readback_map(self):
                current = operator.readback_map(world)
                if current != map_packet:
                    raise ValueError("Native topology changed after survey")
                return current

            def spawn_motor_vehicle(self, position):
                nonlocal vehicle, sensors
                vehicle = operator.spawn_vehicle(world, review["vehicle_blueprint"], position)
                if vehicle is None or not getattr(vehicle, "is_alive", False):
                    raise ValueError("Native vehicle spawn failed")
                if getattr(vehicle, "type_id", None) != review["vehicle_blueprint"]:
                    raise ValueError("spawned blueprint differs from reviewed source")
                callbacks, sensors = operator.cameras(world, vehicle, VIEWS, review)
                if not isinstance(callbacks, dict) or set(callbacks) != set(VIEWS):
                    raise ValueError("four synchronized cameras missing")
                if any(not callable(callbacks[k]) for k in VIEWS):
                    raise ValueError("camera callback missing")
                self.callbacks = callbacks
                self.actor_id = _actor_id(vehicle)
                self.first_time = None
                self.last_native_frame = None
                return vehicle

            def actor_state(self, actor):
                return operator.actor_state(actor)

            def step(self, actor, control):
                index = len(self.frames) if hasattr(self, "frames") else 0
                if not hasattr(self, "frames"):
                    self.frames = []
                operator.apply_control(actor, control)
                native_frame = world.tick()
                snap = world.get_snapshot()
                now = float(snap.timestamp.elapsed_seconds)
                if type(native_frame) is not int or snap.frame != native_frame:
                    raise ValueError("Native tick and snapshot mismatch")
                if self.last_native_frame is not None and native_frame != self.last_native_frame + 1:
                    raise ValueError("Native source frame discontinuity")
                if self.first_time is None:
                    self.first_time = now
                if not math.isfinite(now) or abs(now - self.first_time - index / RATE_HZ) > .005:
                    raise ValueError("Native source time discontinuity")
                self.last_native_frame = native_frame
                row = operator.observe(world, actor, native_frame)
                if not isinstance(row, dict) or row.get("source_frame_id") != native_frame:
                    raise ValueError("original actor readback missing")
                if str(row.get("actor_id")) != self.actor_id:
                    raise ValueError("original actor identity mismatch")
                if row.get("section") not in ("approach", "circulating", "exit"):
                    raise ValueError("original map section missing")
                if type(row.get("lane_id")) is not str or not row["lane_id"]:
                    raise ValueError("original allocated lane ID missing")
                for name in ("x", "y", "z", "speed_mps", "heading_x", "heading_y"):
                    if type(row.get(name)) not in (int, float) or not math.isfinite(row[name]):
                        raise ValueError("original actor geometry missing: " + name)
                if row["speed_mps"] < 0:
                    raise ValueError("original actor speed negative")
                body = row.get("body_vertices_m")
                if not isinstance(body, list) or len(body) < 4:
                    raise ValueError("original actor body missing")
                if any(not isinstance(point, list) or len(point) != 3 or
                       any(type(value) not in (int, float) or not math.isfinite(value) for value in point)
                       for point in body):
                    raise ValueError("original actor body vertices invalid")
                for name in VIEWS:
                    image = self.callbacks[name](native_frame)
                    if type(image) is not bytes or not image:
                        raise ValueError("original synchronized image missing: " + name)
                    folder = output / "cameras" / name
                    folder.mkdir(parents=True, exist_ok=True)
                    (folder / f"{native_frame:06d}.png").write_bytes(image)
                frame = {"frame": index, "source_frame_id": native_frame,
                         "exit_connector_id": row.get("exit_connector_id"),
                         "time_s": round(index / RATE_HZ, 5), "section": row["section"],
                         "lane_id": row["lane_id"], "actor_id": self.actor_id,
                         "x": float(row["x"]), "y": float(row["y"]), "z": float(row["z"]),
                         "speed_mps": float(row["speed_mps"]),
                         "body_vertices_m": body,
                         "heading_x": float(row["heading_x"]),
                         "heading_y": float(row["heading_y"])}
                self.frames.append(frame)
                return frame

            def seal(self, exact_case, topo, frames):
                if len(frames) != FRAME_COUNT or frames != self.frames:
                    raise ValueError("incomplete original Native history")
                if hashlib.sha256(operator.map_bytes(world)).hexdigest() != review["map_sha256"]:
                    raise ValueError("loaded map changed during Native capture")
                packet = {"source_kind": "sealed_native_original_history", "case_id": exact_case,
                          "map_id": topo["map_id"], "map_sha256": topo["map_sha256"],
                          "actor_role": "motor_vehicle_driver", "actor_id": self.actor_id,
                          "operator_intended_exit_role": case["operator_intent_request"],
                          "independent_operator_intent_source_sha256": review["independent_operator_intent"]["source_sha256"],
                          "vehicle_blueprint": vehicle.type_id, "entry_id": review["entry_id"],
                          "exit_id": review["exit_id"],
                          "controller_sha256": review["controller_sha256"],
                          "weather_sha256": review["weather_sha256"],
                          "camera_plan_sha256": review["camera_plan_sha256"], "frames": frames}
                sources = {"map": _save(output, "map", map_packet),
                           "history": _save(output, "history", packet)}
                _save(output, "inventory", {"case_id": exact_case,
                    "source_kind": "original_native", "frame_count": FRAME_COUNT,
                    "camera_views": list(VIEWS), "survey_sha256": survey_sha256,
                    "sources": sources})
                return packet

            def destroy(self, actor):
                actor.destroy()

        result = _module("runner").execute(Adapter(), case, throttle=throttle)
        packet = json.loads((output / "history.json").read_text())
        result = route.verify_original_history(packet, topology, case_id)
        observed_roles = []
        for frame in packet["frames"]:
            if frame["section"] != "circulating":
                continue
            role = ("right" if frame["lane_id"] == topology["right_lane_id"] else
                    "left" if frame["lane_id"] == topology["left_lane_id"] else "unmapped")
            if not observed_roles or observed_roles[-1] != role:
                observed_roles.append(role)
        requested_roles = {"right": ["right"], "left": ["left"],
                           "left_then_right": ["left", "right"],
                           "right_then_left": ["right", "left"],
                           "single_right": ["right"]}[case["roundabout_lane_request"]]
        expected_connector = (None if case["actual_exit_request"] == "no_exit" else
                              topology[case["actual_exit_request"] + "_connector_id"])
        if observed_roles != requested_roles or result["first_observed_exit_connector_id"] != expected_connector:
            raise ValueError("physical route did not realize requested lane sequence and exit connector")
        return result
    finally:
        for sensor in reversed(sensors):
            if sensor is not None:
                try:
                    if hasattr(sensor, "stop"):
                        sensor.stop()
                finally:
                    sensor.destroy()
        if vehicle is not None and getattr(vehicle, "is_alive", False):
            vehicle.destroy()
        world.apply_settings(before)
        restored = world.get_settings()
        if restored.synchronous_mode != before.synchronous_mode or restored.fixed_delta_seconds != before.fixed_delta_seconds:
            raise ValueError("Native settings restoration readback failed")
