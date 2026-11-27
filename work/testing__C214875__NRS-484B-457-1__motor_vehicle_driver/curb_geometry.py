"""Source-gated right-curb and original wheel measurements for NRS 484B.457(1)."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT = "testing__C214875__NRS-484B-457-1__motor_vehicle_driver"
SOURCES = ("native_opendrive_map", "highway_dedication", "curb_survey",
           "local_ordinance", "dot_status", "vehicle_blueprint")
INCH_M = 0.0254


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _point(value):
    if not isinstance(value, list) or len(value) != 2 or any(
            type(x) not in (int, float) or not math.isfinite(x) for x in value):
        raise ValueError("finite surveyed XY point required")
    return tuple(float(x) for x in value)


def _distance(point, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    if length2 <= 1e-8:
        raise ValueError("surveyed curb segment is degenerate")
    t = max(0.0, min(1.0, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length2))
    return math.hypot(point[0] - a[0] - t * dx, point[1] - a[1] - t * dy)


def load_site(packet, case_id):
    packet = Path(packet)
    if packet.is_symlink() or not packet.is_file():
        raise ValueError("original curb site packet missing")
    site = json.loads(packet.read_text())
    if site.get("format") != "worker-right-curb-site-v1" or site.get("case_id") != case_id or \
            not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("original curb site identity differs")
    sources = site.get("sources", {})
    if set(sources) != set(SOURCES):
        raise ValueError("original curb source inventory incomplete")
    for name in SOURCES:
        item = sources[name]
        relative = item.get("path")
        if relative != name + ".source":
            raise ValueError("unsafe original curb source path")
        source = packet.parent / relative
        if source.is_symlink() or not source.is_file() or sha(source) != item.get("sha256"):
            raise ValueError("original curb source hash differs: " + name)
    facts = site.get("reviewed_assertions", {})
    required = ("public_highway", "residence_district", "adjacent_right_curb",
                "ordinary_motor_vehicle", "right_side_default_branch")
    if any(facts.get(name) is not True for name in required):
        raise ValueError("original right-curb default branch not reviewed")
    if facts.get("left_curb_ordinance_applies") is not False or \
            facts.get("angle_parking_ordinance_applies") is not False:
        raise ValueError("original section exception applicability unresolved")
    curb = [_point(value) for value in site.get("right_curb_xy_m", [])]
    if len(curb) < 2 or any(math.dist(a, b) < .1 for a, b in zip(curb, curb[1:])):
        raise ValueError("original right curb survey incomplete")
    parking = [_point(value) for value in site.get("parking_route_xy_m", [])]
    if len(parking) < 2:
        raise ValueError("original parking route incomplete")
    return site


def measure_right_wheels(front_xy, rear_xy, curb_xy):
    """Measure both original right-wheel centers; no legal decision is returned."""
    front, rear = _point(front_xy), _point(rear_xy)
    curb = [_point(value) for value in curb_xy]
    if len(curb) < 2 or math.dist(front, rear) < .25:
        raise ValueError("original wheel axis or curb missing")
    distances = [min(_distance(wheel, a, b) for a, b in zip(curb, curb[1:]))
                 for wheel in (front, rear)]
    tangent = (curb[-1][0] - curb[0][0], curb[-1][1] - curb[0][1])
    axis = (front[0] - rear[0], front[1] - rear[1])
    dot = abs(tangent[0] * axis[0] + tangent[1] * axis[1])
    denom = math.hypot(*tangent) * math.hypot(*axis)
    if denom <= 1e-8:
        raise ValueError("original curb or wheel heading degenerate")
    angle = math.degrees(math.acos(max(-1.0, min(1.0, dot / denom))))
    return {"right_front_distance_m": distances[0],
            "right_rear_distance_m": distances[1],
            "max_right_wheel_distance_inches": max(distances) / INCH_M,
            "wheel_curb_alignment_deg": angle,
            "statutory_distance_inch": 18,
            "legal_parallel_judgment": "unresolved"}


def measure_original(attempt, case_id, *, diagnostic=False):
    """Validate a source-sealed original 20 Hz wheel/activity history."""
    attempt = Path(attempt)
    original = attempt / "original-attempt"
    site = load_site(original / "site.json", case_id)
    motion = original / "wheel-motion.jsonl"
    seal_path = original / "wheel-seal.json"
    mapping_path = original / "frame-map.json"
    for path in (motion, seal_path, mapping_path):
        if path.is_symlink() or not path.is_file():
            raise ValueError("Missing required source: original-attempt/" + path.name)
    seal = json.loads(seal_path.read_text())
    mapping = json.loads(mapping_path.read_text())
    rows = [json.loads(line) for line in motion.read_text().splitlines() if line]
    count = seal.get("frame_count")
    if count not in ((9, 900) if diagnostic else (900,)):
        raise ValueError("original curb diagnostic frame count differs")
    if (seal.get("case_id") != case_id or seal.get("frame_count") != count or
            seal.get("motion_sha256") != sha(motion) or seal.get("site_sha256") != sha(original / "site.json") or
            mapping.get("case_id") != case_id or len(mapping.get("frames", [])) != count or len(rows) != count):
        raise ValueError("original curb source seal or frame count differs")
    first_native = mapping["frames"][0]["native_frame"]
    first_time = mapping["frames"][0]["native_time_s"]
    stopped = []
    parked = []
    stopped_only = []
    measurements = []
    for index, (row, frame) in enumerate(zip(rows, mapping["frames"])):
        if (row.get("case_id") != case_id or row.get("frame") != index or
                row.get("native_frame") != first_native + index or
                frame.get("native_frame") != first_native + index or
                abs(row.get("time_s", -1) - first_time - index / 20) > .005 or
                abs(frame.get("native_time_s", -1) - row["time_s"]) > 1e-4):
            raise ValueError("original curb wheel/frame/time join differs")
        speed = row.get("speed_mps")
        if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
            raise ValueError("original vehicle activity missing")
        if speed <= .1:
            stopped.append(index)
            brake = row.get("parking_brake_applied")
            if type(brake) is not bool:
                raise ValueError("original parking control readback missing")
            (parked if brake else stopped_only).append(index)
            measurements.append(measure_right_wheels(row.get("right_front_wheel_xy_m"),
                                                     row.get("right_rear_wheel_xy_m"),
                                                     site["right_curb_xy_m"]))
    if not stopped:
        raise ValueError("original stopped or parked interval absent")
    plan_path = original / "plan.json"
    if plan_path.is_symlink() or not plan_path.is_file():
        raise ValueError("Missing required source: original-attempt/plan.json")
    plan = json.loads(plan_path.read_text())
    if plan.get("case_id") != case_id or plan.get("activity_request") not in ("park", "stop"):
        raise ValueError("original parking activity plan identity differs")
    if plan["activity_request"] == "park" and not parked:
        raise ValueError("original parking-brake interval absent")
    if plan["activity_request"] == "stop" and not stopped_only:
        raise ValueError("original stopped-without-parking-brake interval absent")
    return {"case_id": case_id, "stopped_frames": stopped,
            "parking_brake_frames": parked, "stopped_without_parking_brake_frames": stopped_only,
            "max_right_wheel_distance_inches": max(m["max_right_wheel_distance_inches"] for m in measurements),
            "max_wheel_curb_alignment_deg": max(m["wheel_curb_alignment_deg"] for m in measurements),
            "source_hashes": {"original-attempt/site.json": sha(original / "site.json"),
                              "original-attempt/plan.json": sha(plan_path),
                              "original-attempt/wheel-motion.jsonl": sha(motion),
                              "original-attempt/wheel-seal.json": sha(seal_path),
                              "original-attempt/frame-map.json": sha(mapping_path)},
            "diagnostic_fixture": diagnostic,
            "physical_acceptance_claimed": False,
            "legal_judgment": "unresolved"}
