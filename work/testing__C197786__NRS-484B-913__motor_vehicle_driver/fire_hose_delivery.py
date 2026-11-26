"""CPU-side construction and original-source checks for NRS 484B.913.

No legal outcome is computed here. The caller must supply an actual Native hose
actor or map object; a scenario flag cannot create or authenticate a hose.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class Point:
    x: float
    y: float


def segment_intersects(a: Point, b: Point, c: Point, d: Point) -> bool:
    """Closed segment intersection, including an endpoint touch."""
    def orient(p: Point, q: Point, r: Point) -> float:
        return (q.x - p.x) * (r.y - p.y) - (q.y - p.y) * (r.x - p.x)

    def on(p: Point, q: Point, r: Point) -> bool:
        return min(p.x, q.x) <= r.x <= max(p.x, q.x) and min(p.y, q.y) <= r.y <= max(p.y, q.y)

    values = (orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b))
    if values[0] * values[1] < 0 and values[2] * values[3] < 0:
        return True
    return any((v == 0 and on(p, q, r)) for v, p, q, r in (
        (values[0], a, b, c), (values[1], a, b, d),
        (values[2], c, d, a), (values[3], c, d, b)))


def point_in_polygon(point: Point, corners: Sequence[Point]) -> bool:
    """Closed polygon containment, used only for physical footprint contact."""
    inside = False
    for a, b in zip(corners, (*corners[1:], corners[0])):
        if segment_intersects(a, b, point, point):
            return True
        if (a.y > point.y) != (b.y > point.y):
            x_at_y = a.x + (point.y - a.y) * (b.x - a.x) / (b.y - a.y)
            if point.x < x_at_y:
                inside = not inside
    return inside


def body_over_hose_frames(packet: Mapping[str, Any], case_id: str,
                          *, expected_frames: int = 900) -> list[int]:
    """Measure actual sampled body footprint versus original hose segment.

    This reports geometry, not whether a legal violation occurred. A complete
    original history is required; the centerline diagnostic is insufficient.
    """
    inspect_saved_hose(packet, case_id)
    rows = packet["native"]["frames"]
    if len(rows) != expected_frames:
        raise ValueError("complete original 20 Hz frame history required")
    h0, h1 = (Point(*p) for p in packet["hose"]["segment_xy"])
    hits = []
    for row in rows:
        raw = row.get("ego_body_corners_xy")
        if not isinstance(raw, list) or len(raw) < 4 or any(
                not isinstance(p, list) or len(p) != 2 for p in raw):
            raise ValueError("original ego body footprint missing")
        corners = [Point(*p) for p in raw]
        if any(segment_intersects(a, b, h0, h1)
               for a, b in zip(corners, (*corners[1:], corners[0]))) or point_in_polygon(h0, corners) or point_in_polygon(h1, corners):
            hits.append(row["frame"])
    return hits


def require_hose_source(world: Any, actor_id: int, expected_blueprint: str) -> Any:
    """Resolve the actual prop readback; never synthesize a hose by label."""
    if not expected_blueprint or "hose" not in expected_blueprint.lower():
        raise ValueError("hose blueprint identity missing")
    actor = world.get_actor(actor_id)
    if actor is None or actor.type_id != expected_blueprint:
        raise ValueError("Native hose actor readback mismatch")
    if not actor.is_alive:
        raise ValueError("Native hose actor is not alive")
    return actor


def select_hose_blueprint(world: Any, blueprint_id: str) -> Any:
    """Require a hose-specific blueprint in the local CARLA asset library."""
    if not blueprint_id or "hose" not in blueprint_id.lower():
        raise ValueError("hose-specific asset id required")
    blueprint = world.get_blueprint_library().find(blueprint_id)
    if blueprint is None or blueprint.id != blueprint_id:
        raise ValueError("hose-specific Native asset unavailable")
    return blueprint


def construct_hose(world: Any, blueprint_id: str, transform: Any) -> Any:
    """Spawn and read back the specified hose asset at its actual Native pose."""
    blueprint = select_hose_blueprint(world, blueprint_id)
    actor = world.try_spawn_actor(blueprint, transform)
    if actor is None:
        raise ValueError("Native hose spawn failed")
    return require_hose_source(world, actor.id, blueprint_id)


def inspect_saved_hose(packet: Mapping[str, Any], case_id: str) -> dict[str, Any]:
    """Reject missing source histories and report physical facts without verdicts."""
    if packet.get("case_id") != case_id:
        raise ValueError("exact case identity mismatch")
    native = packet.get("native")
    if not isinstance(native, Mapping) or not native.get("result_sha256"):
        raise ValueError("sealed Native result hash missing")
    frames = native.get("frames")
    if not isinstance(frames, Sequence) or len(frames) < 2:
        raise ValueError("original frame history missing")
    for key in ("hose", "road", "incident", "command_official", "consent", "vehicle"):
        source = packet.get(key)
        if not isinstance(source, Mapping) or not source.get("source_path") or not source.get("sha256"):
            raise ValueError(f"{key} original source binding missing")
    hose = packet["hose"]
    endpoints = hose.get("segment_xy")
    if not isinstance(endpoints, list) or len(endpoints) != 2 or any(len(p) != 2 for p in endpoints):
        raise ValueError("hose original geometry missing")
    h0, h1 = (Point(*p) for p in endpoints)
    if hypot(h1.x - h0.x, h1.y - h0.y) <= 0:
        raise ValueError("hose has zero length")
    positions = []
    last_frame = -1
    last_time = None
    for row in frames:
        if not isinstance(row, Mapping) or not isinstance(row.get("ego_xy"), list) or len(row["ego_xy"]) != 2:
            raise ValueError("original ego position missing")
        frame = row.get("frame")
        if not isinstance(frame, int) or frame <= last_frame:
            raise ValueError("original frame order invalid")
        time_seconds = row.get("elapsed_seconds")
        if not isinstance(time_seconds, (int, float)):
            raise ValueError("original elapsed-time source missing")
        if last_time is not None and (frame != last_frame + 1 or abs(time_seconds - last_time - 0.05) > 0.001):
            raise ValueError("original 20 Hz frame cadence invalid")
        last_frame = frame
        last_time = time_seconds
        positions.append(Point(*row["ego_xy"]))
    crossings = [frames[i + 1]["frame"] for i in range(len(positions) - 1)
                 if segment_intersects(positions[i], positions[i + 1], h0, h1)]
    if hose.get("fire_department_affiliation") is not True:
        raise ValueError("fire department hose affiliation unproven")
    if packet["road"].get("private_way_owner") is None or packet["road"].get("permitted_access") is None:
        raise ValueError("private way ownership or permitted access unproven")
    if packet["incident"].get("purpose") not in ("fire", "alarm", "practice"):
        raise ValueError("qualifying incident purpose unproven")
    if packet["vehicle"].get("ordinary_motor_vehicle") is not True or packet["vehicle"].get("human_driver") is not True:
        raise ValueError("vehicle or human driver identity unproven")
    official = packet["command_official"]
    if official.get("in_command") is not True or not official.get("identity"):
        raise ValueError("command official identity or status unproven")
    consent = packet["consent"]
    if consent.get("status") not in ("given", "withheld", "none"):
        raise ValueError("command-official consent status unproven")
    if consent.get("status") == "given" and (consent.get("official_identity") != official["identity"]
                                              or not consent.get("scope") or consent.get("frame") is None):
        raise ValueError("consent source, scope or timing unproven")
    if hose.get("protection") not in ("unprotected", "protected"):
        raise ValueError("hose protection arrangement unproven")
    return {"crossing_frames": crossings, "hose_protection": hose["protection"],
            "incident_purpose": packet["incident"]["purpose"], "consent_status": consent["status"],
            "consent_frame": consent.get("frame"), "official_identity": official["identity"],
            "legal_verdict": None}


def compare_saved_hose(a: Mapping[str, Any], b: Mapping[str, Any], variable: str) -> dict[str, Any]:
    """Require a controlled pair with independent sealed Native sources."""
    if variable not in ("consent", "protection", "passage", "incident_purpose"):
        raise ValueError("undeclared comparison variable")
    if a.get("native", {}).get("result_sha256") == b.get("native", {}).get("result_sha256"):
        raise ValueError("independent Native attempts required")
    a_facts = inspect_saved_hose(a, a.get("case_id"))
    b_facts = inspect_saved_hose(b, b.get("case_id"))
    keys = {"consent": "consent", "protection": "hose", "passage": "native", "incident_purpose": "incident"}
    differing = keys[variable]
    def payload(source: Mapping[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in source.items() if key not in ("source_path", "sha256")}

    for key in ("road", "vehicle", "command_official"):
        if payload(a.get(key, {})) != payload(b.get(key, {})):
            raise ValueError(f"fixed {key} context changed")
    for key in ("hose", "incident", "consent"):
        if key != differing and payload(a.get(key, {})) != payload(b.get(key, {})):
            raise ValueError(f"fixed {key} condition changed")
    if variable == "consent" and a["consent"].get("status") == b["consent"].get("status"):
        raise ValueError("consent contrast absent")
    if variable == "protection" and a["hose"].get("protection") == b["hose"].get("protection"):
        raise ValueError("protection contrast absent")
    if variable == "incident_purpose" and a["incident"].get("purpose") == b["incident"].get("purpose"):
        raise ValueError("incident-purpose contrast absent")
    if variable == "passage" and bool(a_facts["crossing_frames"]) == bool(b_facts["crossing_frames"]):
        raise ValueError("physical-passage contrast absent")
    return {"comparison_variable": variable, "observed_a": a_facts,
            "observed_b": b_facts, "legal_verdict": None}
