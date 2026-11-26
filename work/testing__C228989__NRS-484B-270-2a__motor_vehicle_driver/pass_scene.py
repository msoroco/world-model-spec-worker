"""Source-gated Native lane and actor construction for NRS 484B.270(2)(a).

The packet is a reviewed survey of the actual Native map. A request for an open
left lane is only a scene request; this module cannot decide legal availability,
reasonable safety, due care, or whether a later pass physically succeeded.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


KINDS = {"bicycle", "electric_bicycle", "electric_scooter"}


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _point(value):
    _need(isinstance(value, list) and len(value) == 2 and
          all(type(v) in (int, float) and math.isfinite(v) for v in value),
          "finite surveyed world XY required")
    return tuple(float(v) for v in value)


def _sealed(packet_path, ref):
    base = Path(packet_path).resolve().parent
    path = (base / ref["path"]).resolve()
    _need(path.is_relative_to(base) and path.is_file(), "missing reviewed source")
    _need(hashlib.sha256(path.read_bytes()).hexdigest() == ref["sha256"],
          "reviewed source hash mismatch")
    return path


def validate(packet_path, case, *, allow_synthetic=False):
    """Validate exact case, source seals, surveyed topology and spawn geometry."""
    packet = json.loads(Path(packet_path).read_text(encoding="utf-8"))
    _need(packet.get("case_id") == case.get("case_id") and
          packet.get("cell_id") == "C228989" and
          packet.get("actor") == "motor_vehicle_driver", "exact Native case mismatch")
    _need(packet.get("source_kind") == "reviewed_original_native_map" or
          (allow_synthetic and packet.get("source_kind") == "synthetic_cpu_fixture"),
          "reviewed original Native map packet required")
    refs = packet.get("source_refs")
    _need(isinstance(refs, list) and len(refs) >= 3, "map, lanes and actors need source seals")
    for ref in refs:
        _sealed(packet_path, ref)
    _need(packet.get("map_name") and packet.get("ego_blueprint_id", "").startswith("vehicle.") and
          packet.get("control_blueprint_id") and packet.get("ego_driver_source") and
          packet.get("control_rider_source"), "map, blueprints and human identities required")
    _need(packet.get("control_kind") in KINDS and
          packet["control_kind"] == case.get("control_kind"), "qualifying control kind mismatch")
    lanes = packet.get("lanes")
    _need(isinstance(lanes, list) and lanes, "surveyed lane inventory required")
    by_id = {lane.get("lane_id"): lane for lane in lanes}
    _need(None not in by_id and len(by_id) == len(lanes), "distinct surveyed lane IDs required")
    ego_lane = packet.get("ego_lane_id")
    left_lane = packet.get("immediate_left_lane_id")
    _need(ego_lane in by_id and by_id[ego_lane].get("travel_direction") == "forward",
          "forward ego lane required")
    forward = [lane for lane in lanes if lane.get("travel_direction") == "forward"]
    _need(len(forward) == case.get("same_direction_lane_count_requested"),
          "source same-direction lane count mismatch")
    if len(forward) == 2:
        _need(left_lane in by_id and left_lane != ego_lane and
              by_id[left_lane].get("travel_direction") == "forward" and
              by_id[ego_lane].get("immediate_left_lane_id") == left_lane,
              "immediate-left same-direction adjacency required")
    else:
        _need(left_lane is None, "one-lane scene cannot claim immediate-left lane")
    for lane in lanes:
        _need(lane.get("source_ref") and lane.get("native_road_id") is not None and
              lane.get("native_lane_id") is not None and lane.get("travel_direction") in
              {"forward", "reverse"}, "source-backed Native lane identity required")
    positions = packet.get("spawn_xy")
    _need(isinstance(positions, dict), "surveyed spawn positions required")
    ego = _point(positions.get("ego"))
    control = _point(positions.get("control"))
    axis = _point(packet.get("road_forward"))
    _need(abs(math.hypot(*axis) - 1) <= .02, "unit road direction required")
    gap = sum((control[i] - ego[i]) * axis[i] for i in range(2))
    _need(gap > 5, "qualifying control must spawn ahead")
    traffic = case.get("left_lane_traffic_requested")
    if traffic == "occupied":
        _need(left_lane and packet.get("occupant_blueprint_id", "").startswith("vehicle.") and
              packet.get("occupant_lane_id") == left_lane,
              "occupied left-lane actor required")
        _point(positions.get("occupant"))
    else:
        _need("occupant" not in positions and packet.get("occupant_lane_id") is None,
              "open or one-lane control must not spawn left occupant")
    _need(packet.get("lane_restrictions_source") and
          packet.get("lane_obstructions_source") and
          packet.get("surrounding_traffic_source"),
          "availability source inventory required")
    return packet


def construct(adapter, packet_path, case, *, allow_synthetic=False):
    """Spawn surveyed actors. Caller owns returned actors and destroys in reverse order."""
    packet = validate(packet_path, case, allow_synthetic=allow_synthetic)
    _need(getattr(adapter, "native_attested", False) is True or allow_synthetic,
          "attested Native adapter required")
    _need(adapter.map_name() == packet["map_name"], "Native map readback mismatch")
    owned = []
    try:
        roles = [("ego", packet["ego_blueprint_id"], packet["ego_lane_id"]),
                 ("control", packet["control_blueprint_id"], packet["ego_lane_id"])]
        if case["left_lane_traffic_requested"] == "occupied":
            roles.append(("occupant", packet["occupant_blueprint_id"],
                          packet["immediate_left_lane_id"]))
        actors = {}
        for role, blueprint, lane_id in roles:
            xy = packet["spawn_xy"][role]
            lane = next(row for row in packet["lanes"] if row["lane_id"] == lane_id)
            observed = adapter.lane_at(xy)
            _need(observed == (lane["native_road_id"], lane["native_lane_id"]),
                  "Native waypoint lane readback mismatch: " + role)
            actor = adapter.spawn(blueprint, xy, packet["spawn_yaw_deg"])
            _need(actor is not None, "Native actor spawn failed: " + role)
            owned.append(actor)
            _need(adapter.actor_blueprint(actor) == blueprint and
                  adapter.actor_lane(actor) == observed,
                  "Native actor identity or lane readback mismatch: " + role)
            actors[role] = actor
        return {"actors": actors, "owned": owned, "packet": packet,
                "legal_availability": None, "legal_reasonable_safety": None,
                "legal_due_care": None}
    except BaseException:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise
