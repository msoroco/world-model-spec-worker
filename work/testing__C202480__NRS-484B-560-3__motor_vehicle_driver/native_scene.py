"""CARLA-lazy construction of a source-bound railroad crossing stop scene.

The site packet must be reviewed separately. Successful construction only
requests the scene; physical realization and legal judgment remain unverified.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


SOURCE_NAMES = ("opendrive", "crossing_authority", "lane_markings",
                "highway_boundary", "right_side_constraints", "camera_poses")


def _finite(value: object, name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("invalid site coordinate: " + name)
    return float(value)


def _source(path: Path, spec: dict, name: str) -> bytes:
    if not isinstance(spec, dict) or not isinstance(spec.get("path"), str):
        raise ValueError("missing reviewed site source: " + name)
    relative = Path(spec["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("site source must stay with packet: " + name)
    source = path.parent / relative
    if not source.is_file():
        raise ValueError("missing reviewed site source: " + name)
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != spec.get("sha256"):
        raise ValueError("site source hash differs: " + name)
    return data


def inspect(packet_path: Path, plan_path: Path, case_id: str) -> tuple[dict, dict, bytes]:
    """Check exact plan and source-linked site geometry before Native connection."""
    packet_path, plan_path = Path(packet_path), Path(plan_path)
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    case = next((item for item in plan["cases"] if item["case_id"] == case_id), None)
    if case is None or packet.get("case_id") != case_id:
        raise ValueError("site packet does not select exact case")
    if packet.get("format") != "c202480-reviewed-crossing-site-v1":
        raise ValueError("reviewed crossing site packet format required")
    sources = packet.get("sources")
    if not isinstance(sources, dict) or set(sources) != set(SOURCE_NAMES):
        raise ValueError("all five reviewed site sources required")
    data = {name: _source(packet_path, sources[name], name) for name in SOURCE_NAMES}
    try:
        authority = json.loads(data["crossing_authority"])
        markings = json.loads(data["lane_markings"])
        boundary = json.loads(data["highway_boundary"])
        constraints = json.loads(data["right_side_constraints"])
        camera_poses = json.loads(data["camera_poses"])
    except (ValueError, UnicodeError) as error:
        raise ValueError("reviewed crossing sources must be structured records") from error
    if packet.get("stopping_required_context") != "reviewed_crossing_instruction":
        raise ValueError("crossing stop authority remains unreviewed")
    if not packet.get("sign_landmark_id") or not packet.get("rail_crossing_map_ref"):
        raise ValueError("crossing device or rail geometry identity missing")
    if (authority.get("governs_crossing") is not True or
            authority.get("sign_landmark_id") != packet["sign_landmark_id"] or
            authority.get("rail_crossing_map_ref") != packet["rail_crossing_map_ref"] or
            authority.get("stop_line_x_m") != packet.get("stop_line_x_m") or
            authority.get("rail_line_x_m") != packet.get("rail_line_x_m")):
        raise ValueError("crossing stop authority source differs from construction")
    lanes = packet.get("marked_lanes")
    if not isinstance(lanes, list) or len(lanes) != case["marked_highway_lane_count"]:
        raise ValueError("total marked highway lane count differs from exact case")
    if any(not isinstance(lane, dict) for lane in lanes):
        raise ValueError("marked lane record missing")
    if len({lane.get("lane_id") for lane in lanes if isinstance(lane, dict)}) != len(lanes):
        raise ValueError("marked lane identities are not unique")
    if any(not lane.get("marking_source_ref") or
           lane.get("direction") not in (-1, 1) for lane in lanes):
        raise ValueError("marked lane direction or source missing")
    if markings.get("marked_lanes") != lanes:
        raise ValueError("marked highway lanes differ from source")
    direction = packet.get("approach_direction")
    if direction not in (-1, 1) or not any(lane["direction"] == direction for lane in lanes):
        raise ValueError("approach direction lacks a marked travel lane")
    stop_x = _finite(packet.get("stop_line_x_m"), "stop line")
    rail_x = _finite(packet.get("rail_line_x_m"), "rail line")
    if direction * (rail_x - stop_x) <= 0:
        raise ValueError("stop line is not before the rail crossing")
    right_y = _finite(packet.get("highway_right_y_m"), "highway right boundary")
    left_y = _finite(packet.get("highway_left_y_m"), "highway left boundary")
    if (boundary.get("highway_right_y_m") != right_y or
            boundary.get("highway_left_y_m") != left_y):
        raise ValueError("highway boundaries differ from source")
    if direction * (left_y - right_y) <= 0:
        raise ValueError("highway boundary coordinates are reversed")
    low_y, high_y = sorted((right_y, left_y))
    slots = packet.get("slots")
    if not isinstance(slots, dict) or not slots:
        raise ValueError("reviewed actor placement slots required")
    if (constraints.get("slots") != slots or
            constraints.get("rightmost_feasible_slot") != packet.get("rightmost_feasible_slot")):
        raise ValueError("right-side constraints differ from source")
    if camera_poses.get("cameras") != packet.get("cameras"):
        raise ValueError("four-view camera poses differ from source")
    from native_camera import validate_plan
    validate_plan(packet_path)
    for name, slot in slots.items():
        if not isinstance(slot, dict):
            raise ValueError("invalid actor placement slot: " + name)
        x, y = _finite(slot.get("x_m"), name + " x"), _finite(slot.get("y_m"), name + " y")
        if direction * (stop_x - x) <= 0 or not low_y < y < high_y:
            raise ValueError("actor spawn is not on the approach within highway bounds")
    ego_slot = packet.get("ego_slot")
    right_slot = packet.get("rightmost_feasible_slot")
    companion_slot = packet.get("companion_slot")
    if ego_slot not in slots or right_slot not in slots:
        raise ValueError("subject/right-side slot binding missing")
    right_value = slots[right_slot]["y_m"]
    if any(direction * (slot["y_m"] - right_value) < 0 for slot in slots.values()):
        raise ValueError("declared rightmost feasible slot is not rightmost in packet")
    if case["subject_lateral_plan"] == "rightmost_feasible" and ego_slot != right_slot:
        raise ValueError("subject is not in authored rightmost feasible slot")
    if case["subject_lateral_plan"] == "left_of_feasible" and ego_slot == right_slot:
        raise ValueError("left-placement probe lacks lateral contrast")
    two = case["traffic_arrangement"] == "two_queues"
    if two and (companion_slot not in slots or companion_slot == ego_slot):
        raise ValueError("two-queue probe lacks adjacent actor slot")
    if not two and companion_slot is not None:
        raise ValueError("one-queue probe adds an adjacent actor")
    if two and abs(slots[ego_slot]["y_m"] - slots[companion_slot]["y_m"]) < 2.0:
        raise ValueError("adjacent vehicle footprints cannot form separate queues")
    blueprints = packet.get("vehicle_blueprints")
    if not isinstance(blueprints, dict) or not blueprints.get("ego") or (
            two and not blueprints.get("companion")):
        raise ValueError("reviewed motor vehicle blueprints required")
    return packet, case, data["opendrive"]


class Scene:
    def __init__(self, ego, companion, packet: dict):
        self.ego, self.companion, self.packet = ego, companion, packet

    def close(self) -> None:
        for actor in (self.companion, self.ego):
            if actor is not None:
                actor.destroy()


def create(world, packet_path: Path, plan_path: Path, case_id: str,
           transform_factory) -> Scene:
    """Check live map/landmark identity and actually spawn the requested actors."""
    packet, case, opendrive = inspect(packet_path, plan_path, case_id)
    live_map = world.get_map()
    if hashlib.sha256(live_map.to_opendrive().encode()).digest() != hashlib.sha256(opendrive).digest():
        raise ValueError("live Native OpenDRIVE differs from reviewed source")
    landmarks = {str(item.id) for item in live_map.get_all_landmarks()}
    if str(packet["sign_landmark_id"]) not in landmarks:
        raise ValueError("reviewed crossing sign landmark absent from Native map")
    library = world.get_blueprint_library()
    spawned = []
    try:
        for role, slot_name in (("ego", packet["ego_slot"]),
                                ("companion", packet.get("companion_slot"))):
            if slot_name is None:
                continue
            slot = packet["slots"][slot_name]
            blueprint = library.find(packet["vehicle_blueprints"][role])
            transform = transform_factory(slot["x_m"], slot["y_m"],
                                          _finite(slot.get("z_m", 0), "spawn z"),
                                          0 if packet["approach_direction"] == 1 else 180)
            actor = world.try_spawn_actor(blueprint, transform)
            if actor is None:
                raise ValueError("Native vehicle spawn failed: " + role)
            spawned.append(actor)
    except Exception:
        for actor in reversed(spawned):
            actor.destroy()
        raise
    expected = 2 if case["traffic_arrangement"] == "two_queues" else 1
    if len(spawned) != expected:
        raise ValueError("Native actor count differs")
    return Scene(spawned[0], spawned[1] if expected == 2 else None, packet)
