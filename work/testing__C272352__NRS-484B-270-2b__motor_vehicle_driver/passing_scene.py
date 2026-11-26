"""Source-sealed one-lane passing scene construction for C272352.

The survey must come from the original Native map. Synthetic packets are accepted
only by explicit CPU tests; they cannot establish a real highway or safe pass.
"""

import hashlib
import json
import math
from pathlib import Path


KINDS = {"bicycle", "electric_bicycle", "electric_scooter"}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def point(value):
    need(isinstance(value, list) and len(value) == 2 and all(
        type(x) in (int, float) and math.isfinite(x) for x in value),
        "finite surveyed XY required")
    return tuple(float(x) for x in value)


def validate(packet_path, case, *, synthetic=False):
    path = Path(packet_path).resolve()
    packet = json.loads(path.read_text(encoding="utf-8"))
    need(packet.get("case_id") == case["case_id"] and
         packet.get("cell_id") == "C272352", "exact case/site mismatch")
    need(packet.get("target_clearance_m") == case["target_clearance_m"],
         "reviewed target clearance mismatch")
    need(packet.get("source_kind") == "reviewed_original_native_map" or
         (synthetic and packet.get("source_kind") == "synthetic_cpu_fixture"),
         "reviewed original Native map required")
    refs = packet.get("source_refs")
    need(isinstance(refs, list) and len(refs) >= 3,
         "map, lane and traffic source seals required")
    need({"map", "lane", "traffic"} <= {ref.get("role") for ref in refs},
         "map, lane and traffic source roles required")
    for ref in refs:
        source = (path.parent / ref["path"]).resolve()
        need(source.is_relative_to(path.parent) and source.is_file(),
             "missing source-sealed site input")
        need(hashlib.sha256(source.read_bytes()).hexdigest() == ref["sha256"],
             "stale source-sealed site input")
    need(packet.get("public_highway_source") and packet.get("map_name") and
         packet.get("centerline_source") and packet.get("zone_source") and
         packet.get("opposing_traffic_source") and
         packet.get("exception_213_217_source"),
         "highway, controls and incorporated exceptions need source review")
    need(type(packet.get("centerline_y")) in (int, float) and
         type(packet.get("right_side_y")) in (int, float) and
         math.isfinite(packet["centerline_y"]) and math.isfinite(packet["right_side_y"]),
         "source-measured highway lateral references required")
    lanes = packet.get("lanes")
    need(isinstance(lanes, list) and lanes, "surveyed lanes required")
    same = [x for x in lanes if x.get("direction") == "forward"]
    need(len(same) == 1, "exactly one same-direction lane required")
    ego_lane = same[0]
    need(ego_lane.get("native_road_id") is not None and
         ego_lane.get("native_lane_id") is not None and
         ego_lane.get("source_ref"), "Native lane identity/source required")
    need(packet.get("ego_blueprint_id", "").startswith("vehicle.") and
         packet.get("control_blueprint_id") and
         packet.get("control_kind") in KINDS and
         packet["control_kind"] == case["control_kind"],
         "qualifying source-backed participant identities required")
    need(packet.get("ego_driver_source") and packet.get("control_rider_source"),
         "driver and rider classification sources required")
    positions = packet.get("spawn_xy")
    need(isinstance(positions, dict), "surveyed spawns required")
    ego, control = point(positions.get("ego")), point(positions.get("control"))
    axis = point(packet.get("road_forward"))
    need(abs(math.hypot(*axis) - 1) < .02, "unit route direction required")
    need(sum((control[i] - ego[i]) * axis[i] for i in range(2)) > 5,
         "qualifying control must start ahead")
    need(packet.get("route_xy") and len(packet["route_xy"]) >= 3,
         "surveyed passing route required")
    for xy in packet["route_xy"]:
        point(xy)
    return packet


def construct(adapter, packet_path, case, *, synthetic=False):
    """Spawn source-checked ego/control; caller owns returned actors."""
    packet = validate(packet_path, case, synthetic=synthetic)
    need(synthetic or getattr(adapter, "native_attested", False) is True,
         "attested Native adapter required")
    need(adapter.map_name() == packet["map_name"], "Native map readback mismatch")
    lane = next(x for x in packet["lanes"] if x["direction"] == "forward")
    expected = (lane["native_road_id"], lane["native_lane_id"])
    owned = []
    try:
        for role in ("ego", "control"):
            xy = packet["spawn_xy"][role]
            need(adapter.lane_at(xy) == expected,
                 "Native waypoint lane readback mismatch: " + role)
            blueprint = packet[role + "_blueprint_id"]
            actor = adapter.spawn(blueprint, xy, packet["spawn_yaw_deg"])
            need(actor is not None, "Native spawn failed: " + role)
            owned.append(actor)
            need(adapter.actor_blueprint(actor) == blueprint and
                 adapter.actor_lane(actor) == expected,
                 "Native actor identity/lane readback mismatch: " + role)
        return {"ego": owned[0], "control": owned[1], "owned": owned,
                "survey": packet, "legal_safety": None}
    except BaseException:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise
