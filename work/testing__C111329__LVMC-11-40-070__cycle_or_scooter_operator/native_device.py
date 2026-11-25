"""Source-gated Native device-site construction and original-history measurement.

A site inventory is captured by a local operator from the selected map. No map or
blueprint claim is inferred from the frozen catalog or a synthetic fixture.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

VALID_DEVICES = {"signal", "stop_sign", "other_control_device"}
VALID_DIRECTIONS = {"stop", "proceed", "none"}


def read_site(path: Path, expected_sha256: str, *, allow_diagnostic: bool = False) -> dict:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("original Native site hash mismatch")
    site = json.loads(raw)
    if site.get("source_kind") != "original_local_native_site_inventory":
        raise ValueError("unverified Native site inventory")
    if site.get("diagnostic_fixture") and not allow_diagnostic:
        raise ValueError("diagnostic fixture cannot be an original Native site")
    for key in ("map_name", "jurisdiction_source", "governed_approach", "stop_line", "vehicle_route", "device_id", "device_type", "device_authority_source", "vehicle_applicability_source", "bike_blueprint_id", "participant_class", "classification_source"):
        if not site.get(key):
            raise ValueError("missing Native site field: " + key)
    if site["participant_class"] != "human_powered_bicycle":
        raise ValueError("selected witness requires a human-powered bicycle")
    if site["device_type"] not in VALID_DEVICES:
        raise ValueError("unsupported official device type")
    if len(site["vehicle_route"]) < 2 or len(site["stop_line"]) != 2:
        raise ValueError("incomplete route or stop line")
    try:
        route = [[float(v) for v in point] for point in site["vehicle_route"]]
        line = [[float(v) for v in point] for point in site["stop_line"]]
        if any(len(point) != 3 for point in route) or any(len(point) != 2 for point in line):
            raise ValueError("invalid original route or stop-line dimensions")
        if not all(math.isfinite(v) for point in route + line for v in point):
            raise ValueError("nonfinite original route or stop line")
        if math.dist(line[0], line[1]) < 0.1:
            raise ValueError("degenerate original stop line")
        if math.dist(route[0][:2], route[1][:2]) < 1.0:
            raise ValueError("degenerate original route")
        x0, y0 = line[0]
        x1, y1 = line[1]
        side = lambda point: (x1-x0)*(point[1]-y0)-(y1-y0)*(point[0]-x0)
        if side(route[0]) * side(route[1]) >= 0:
            raise ValueError("original route does not cross governing stop line")
    except (TypeError, ValueError) as error:
        raise ValueError("invalid original route or stop-line geometry") from error
    return site


def construct(world, carla, site: dict, case: dict):
    """Spawn read-back bicycle and select an original governed signal/sign.

    Device authority and applicability are local source packets, never inferred
    from the CARLA actor label. Officer direction needs an independent local
    authority packet and a real actor/trace; absent support fails closed.
    """
    if site.get("map_name") != world.get_map().name:
        raise ValueError("Native map identity mismatch")
    if site["device_type"] != case["device_type"]:
        raise ValueError("case device type differs from source site")
    if case.get("officer_direction", "none") not in VALID_DIRECTIONS:
        raise ValueError("unsupported officer direction")
    if case.get("officer_direction", "none") != "none" and not site.get("police_authority_source"):
        raise ValueError("missing original Police Officer authority source")
    controls = {str(x.id): x for x in world.get_actors()}
    device = controls.get(site["device_id"])
    if device is None or not getattr(device, "is_alive", False):
        raise ValueError("governing Native device unavailable")
    library = world.get_blueprint_library()
    blueprint = library.find(site["bike_blueprint_id"])
    if blueprint is None or blueprint.id != site["bike_blueprint_id"]:
        raise ValueError("bicycle Native blueprint unavailable")
    origin = site["vehicle_route"][0]
    transform = carla.Transform(carla.Location(x=float(origin[0]), y=float(origin[1]), z=float(origin[2])))
    bike = world.spawn_actor(blueprint, transform)
    if bike is None:
        raise RuntimeError("bicycle spawn failed")
    try:
        if bike.type_id != site["bike_blueprint_id"] or not bike.is_alive:
            raise ValueError("bicycle Native actor readback mismatch")
        if bike.get_transform().location.distance(transform.location) > 1.0:
            raise ValueError("bicycle spawn location readback mismatch")
        return {"bike": bike, "device": device, "owned_actors": [bike], "route": site["vehicle_route"]}
    except BaseException:
        bike.destroy()
        raise


def audit_original_history(case: dict, site: dict, samples: list[dict]) -> dict:
    """Validate source-bound 20 Hz event sequence; report facts, no legal label."""
    if len(samples) < 2 or any(s.get("source_kind") != "original_native" for s in samples):
        raise ValueError("missing original Native samples")
    required = ("frame", "time_s", "bike_id", "bike_blueprint_id", "device_id", "device_state", "bike_front_xy", "officer_actor_id", "officer_command", "officer_authority_source")
    for i, s in enumerate(samples):
        if any(k not in s for k in required):
            raise ValueError("incomplete original Native sample")
        if s["bike_blueprint_id"] != site["bike_blueprint_id"] or s["device_id"] != site["device_id"]:
            raise ValueError("participant or device source mismatch")
        if i:
            prev = samples[i - 1]
            if s["frame"] != prev["frame"] + 1 or not 0.04 <= s["time_s"] - prev["time_s"] <= 0.06:
                raise ValueError("frame or 20 Hz time discontinuity")
            if s["bike_id"] != prev["bike_id"]:
                raise ValueError("bicycle actor identity changed")
        if case.get("officer_direction", "none") != "none":
            if not s["officer_actor_id"] or s["officer_authority_source"] != site.get("police_authority_source"):
                raise ValueError("Police Officer identity or authority not measured")
            if s["officer_command"] not in ("none", case["officer_direction"]):
                raise ValueError("officer command differs from case")
        elif s["officer_command"] != "none":
            raise ValueError("undeclared officer command")
    x0, y0 = map(float, site["stop_line"][0]); x1, y1 = map(float, site["stop_line"][1])
    def side(s):
        x, y = map(float, s["bike_front_xy"])
        return (x1-x0)*(y-y0)-(y1-y0)*(x-x0)
    sides = [side(s) for s in samples]
    crossing = next((i for i in range(1, len(sides)) if sides[i-1]*sides[i] < 0), None)
    return {"source_kind": "original_native", "case_id": case["case_id"], "bike_id": samples[0]["bike_id"], "device_id": site["device_id"], "crossing_frame": samples[crossing]["frame"] if crossing is not None else None, "device_state_at_crossing": samples[crossing]["device_state"] if crossing is not None else None, "officer_command_at_crossing": samples[crossing]["officer_command"] if crossing is not None else None, "legal_assessment": "unresolved"}
