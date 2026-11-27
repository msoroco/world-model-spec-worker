"""Reviewed original scene validation and rider-arm construction.

The requested pose is an engineering actuator target. Original joint readback,
road contact, and rendered pixels decide whether a captured attempt realizes it.
"""

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C229813__NRS-484B-769__cycle_or_scooter_operator"
KINDS = ("bicycle", "electric_bicycle", "electric_scooter")
POSTURES = ("horizontal_right_arm", "downward_right_arm", "bent_right_arm")
SOURCES = ("map_opendrive", "highway_status", "roadway_geometry",
           "shoulder_geometry", "operator_identity", "cycle_classification",
           "turn_route", "rider_arm_rig", "camera_sites")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def case_parts(case_id):
    require(case_id.startswith(ASSIGNMENT + "__"), "exact assignment case required")
    suffix = case_id[len(ASSIGNMENT) + 2:]
    for kind in KINDS:
        for posture in POSTURES:
            if suffix == kind + "_" + posture:
                return kind, posture
    raise ValueError("unknown exact signal case")


def _inside(point, polygon):
    x, y = point
    inside = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y):
            if x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]:
                inside = not inside
    return inside


def load_reviewed_scene(packet_path, source_root, case_id):
    """Fail closed before spawning if any original cited source changed."""
    kind, _ = case_parts(case_id)
    packet = json.loads(Path(packet_path).read_text(encoding="utf-8"))
    require(packet.get("source_kind") == "reviewed_original_scene" and
            packet.get("case_id") == case_id, "reviewed exact scene required")
    scene = packet.get("scene")
    require(isinstance(scene, dict), "reviewed scene missing")
    root = Path(source_root).resolve()
    for name in SOURCES:
        binding = packet.get("sources", {}).get(name)
        require(isinstance(binding, dict), "reviewed source binding missing: " + name)
        rel = binding.get("path")
        require(isinstance(rel, str) and rel and not Path(rel).is_absolute(),
                "relative original source path required: " + name)
        target = (root / rel).resolve()
        require(target.is_relative_to(root) and target.is_file() and not target.is_symlink(),
                "original source file missing: " + name)
        digest = sha(target)
        require(digest == binding.get("sha256") == scene.get(name + "_source_sha256"),
                "original source hash differs: " + name)
    require(scene.get("operator_vehicle_kind") == kind and
            scene.get("operator_identity") and scene.get("highway_status") == "highway",
            "covered operator and sourced highway required")
    require(scene.get("roadway_status") == "roadway" and
            scene.get("roadway_polygon") and scene.get("shoulder_polygon"),
            "roadway outside shoulder geometry required")
    route = scene.get("right_turn_route")
    require(isinstance(route, list) and len(route) >= 3,
            "reviewed right-turn waypoint route required")
    for point in route:
        require(isinstance(point, list) and len(point) == 2 and
                all(isinstance(x, (int, float)) and math.isfinite(x) for x in point),
                "finite route waypoints required")
    a = (route[1][0] - route[0][0], route[1][1] - route[0][1])
    b = (route[-1][0] - route[-2][0], route[-1][1] - route[-2][1])
    require(math.hypot(*a) > 1 and math.hypot(*b) > 1 and
            a[0] * b[1] - a[1] * b[0] < -1,
            "reviewed route must turn right")
    require(all(_inside(point, scene["roadway_polygon"]) and
                not _inside(point, scene["shoulder_polygon"]) for point in route),
            "reviewed turn waypoints must remain on roadway outside shoulder")
    rig = scene.get("rider_arm_rig")
    require(isinstance(rig, dict) and
            all(rig.get(j) for j in ("right_shoulder", "right_elbow", "right_wrist")) and
            isinstance(rig.get("mount_offset_m"), list) and
            len(rig["mount_offset_m"]) == 3 and
            all(isinstance(v, (int, float)) and math.isfinite(v) for v in rig["mount_offset_m"]) and
            rig.get("independent_actuation") is True and
            all(isinstance(rig.get("posture_rotations_deg", {}).get(posture), dict) and
                all(isinstance(rig["posture_rotations_deg"][posture].get(rig[j]), list) and
                    len(rig["posture_rotations_deg"][posture][rig[j]]) == 3 and
                    all(isinstance(v, (int, float)) and math.isfinite(v) for v in
                        rig["posture_rotations_deg"][posture][rig[j]])
                    for j in ("right_shoulder", "right_elbow", "right_wrist"))
                for posture in POSTURES),
            "independently actuated original right arm required")
    sites = scene.get("camera_sites")
    require(isinstance(sites, dict) and set(sites) ==
            {"overview", "approach", "reference_corner", "driver_reference"} and
            all(isinstance(pose, list) and len(pose) == 6 and
                all(isinstance(v, (int, float)) and math.isfinite(v) for v in pose)
                for pose in sites.values()),
            "four reviewed original camera poses required")
    require(scene.get("cycle_blueprint_id") and scene.get("rider_blueprint_id"),
            "reviewed cycle and rider blueprints required")
    return scene, sha(packet_path)


def requested_pose(posture):
    """Rider-local right/forward/up offsets in metres, relative to shoulder."""
    require(posture in POSTURES, "known signal posture required")
    return {
        "horizontal_right_arm": {"elbow": [0.32, 0.0, 0.0], "wrist": [0.65, 0.0, 0.0]},
        "downward_right_arm": {"elbow": [0.27, 0.0, -0.22], "wrist": [0.43, 0.0, -0.49]},
        "bent_right_arm": {"elbow": [0.32, 0.0, 0.0], "wrist": [0.39, 0.31, 0.02]},
    }[posture]


def construct(adapter, scene, case_id):
    """Require real arm articulation; never substitute an indicator or label."""
    kind, posture = case_parts(case_id)
    require(scene["operator_vehicle_kind"] == kind, "covered kind differs")
    road = adapter.map_opendrive_bytes()
    require(isinstance(road, bytes) and
            hashlib.sha256(road).hexdigest() == scene["map_opendrive_source_sha256"],
            "live map differs from reviewed source")
    require(adapter.route_readback(scene["right_turn_route"],
                                   scene["roadway_polygon"],
                                   scene["shoulder_polygon"]) is True,
            "roadway right-turn route readback failed")
    require(adapter.supports_arm_rig(scene["rider_blueprint_id"],
                                     scene["rider_arm_rig"]) is True,
            "independent rider arm rig unavailable")
    owned = []
    try:
        cycle = adapter.spawn_cycle(scene["cycle_blueprint_id"],
                                    scene["right_turn_route"][0])
        require(cycle is not None, "covered cycle spawn failed")
        owned.append(cycle)
        rider = adapter.spawn_rider(scene["rider_blueprint_id"], cycle,
                                    scene["operator_identity"], scene["rider_arm_rig"])
        require(rider is not None, "rider spawn failed")
        owned.append(rider)
        adapter.set_cycle_route(cycle, scene["right_turn_route"])
        pose = requested_pose(posture)
        require(adapter.apply_right_arm_pose(rider, scene["rider_arm_rig"], posture, pose) is True,
                "right arm pose actuation failed")
        readback = adapter.read_right_arm_joints(rider, scene["rider_arm_rig"])
        require(isinstance(readback, dict) and
                all(readback.get(j) for j in ("shoulder", "elbow", "wrist")),
                "actual rider joint readback unavailable")
        return {"cycle": cycle, "rider": rider, "owned": owned,
                "requested_posture": posture, "requested_pose": pose,
                "initial_joint_readback": readback}
    except BaseException:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise
