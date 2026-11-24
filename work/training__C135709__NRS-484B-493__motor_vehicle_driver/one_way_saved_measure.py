"""Source-bound factual reducer for NRS 484B.493 left-side standing/parking.

This does not determine official authority, legal standing/parking, or compliance.
All distances and the 0.1 m/s motion diagnostic are engineering observations.
"""
from __future__ import annotations

import hashlib
import json
import math

ASSIGNMENT = "training__C135709__NRS-484B-493__motor_vehicle_driver"
CAMERAS = ("overview", "sign_approach", "sign_face", "parking_side")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _number(value, label: str) -> float:
    require(isinstance(value, (float, int)) and not isinstance(value, bool), label)
    result = float(value)
    require(math.isfinite(result), label)
    return result


def _xy(value, label: str) -> tuple[float, float]:
    require(isinstance(value, list) and len(value) == 2, label)
    return _number(value[0], label), _number(value[1], label)


def measure(raw_frames: bytes, raw_context: bytes) -> dict:
    packet, context = json.loads(raw_frames), json.loads(raw_context)
    require(packet.get("assignment_id") == ASSIGNMENT and context.get("assignment_id") == ASSIGNMENT,
            "assignment mismatch")
    kind = packet.get("source_kind")
    require(kind in ("synthetic_native_sample", "native_saved_sample") and context.get("source_kind") == kind,
            "source kind mismatch")
    for name in ("map_source_sha256", "one_way_designation_source_sha256",
                 "street_boundary_source_sha256", "device_authority_source_sha256",
                 "device_content_source_sha256", "device_erection_source_sha256"):
        require(isinstance(context.get(name), str) and len(context[name]) == 64 and
                all(ch in "0123456789abcdef" for ch in context[name]), name + " missing")
    require(context.get("roadway_is_one_way") is True, "one-way roadway source missing")
    require(context.get("device_erected") is True and context.get("device_official") is True,
            "official erected device source missing")
    require(context.get("notice_prohibits_left_standing_or_parking") is True,
            "left-side prohibition notice missing")
    require(context.get("device_governs_road_id") == context.get("road_id"),
            "device does not govern roadway")
    origin = _xy(context.get("centerline_origin_xy_m"), "centerline origin missing")
    direction = _xy(context.get("permitted_direction_xy"), "permitted direction missing")
    norm = math.hypot(*direction)
    require(norm > 0 and abs(norm - 1) < 1e-6, "permitted direction must be unit length")
    extent = context.get("governed_longitudinal_extent_m")
    require(isinstance(extent, list) and len(extent) == 2, "governed extent missing")
    lo, hi = (_number(x, "governed extent missing") for x in extent)
    require(lo < hi, "governed extent missing")
    half_width = _number(context.get("street_half_width_m"), "street boundary missing")
    require(half_width > 0, "street boundary missing")
    frames = packet.get("frames")
    require(isinstance(frames, list) and len(frames) >= 600, "recording shorter than 30 seconds")
    require(packet.get("vehicle_id"), "vehicle identity missing")
    previous_native = None
    stationary, left, right, straddling, out_of_extent = [], [], [], [], []
    for i, row in enumerate(frames):
        require(row.get("video_frame") == i and abs(_number(row.get("time_s"), "time missing") - i / 20) < 1e-8,
                "noncontiguous 20 Hz frames")
        native = row.get("native_frame")
        require(isinstance(native, int) and (previous_native is None or native > previous_native),
                "Native frame order missing")
        previous_native = native
        require(row.get("vehicle_id") == packet["vehicle_id"], "vehicle identity changed")
        cameras = row.get("camera_native_frames")
        require(isinstance(cameras, dict) and set(cameras) == set(CAMERAS) and
                all(cameras[name] == native for name in CAMERAS), "four-camera frame join missing")
        speed = _number(row.get("speed_mps"), "speed source missing")
        require(speed >= 0, "invalid speed")
        corners = row.get("footprint_corners_xy_m")
        require(isinstance(corners, list) and len(corners) == 4, "vehicle footprint missing")
        along, across = [], []
        for corner in corners:
            x, y = _xy(corner, "vehicle footprint missing")
            dx, dy = x - origin[0], y - origin[1]
            along.append(dx * direction[0] + dy * direction[1])
            across.append(direction[0] * dy - direction[1] * dx)
        require(all(abs(a) <= half_width for a in across), "vehicle outside sourced street boundaries")
        if speed <= 0.1:
            stationary.append(i)
            if min(along) < lo or max(along) > hi:
                out_of_extent.append(i)
            elif min(across) > 0:
                left.append(i)
            elif max(across) < 0:
                right.append(i)
            else:
                straddling.append(i)
    return {
        "format": "nrs-484b-493-saved-side-diagnostic-v1",
        "assignment_id": ASSIGNMENT, "source_kind": kind,
        "frames_sha256": sha(raw_frames), "context_sha256": sha(raw_context),
        "frame_count": len(frames), "duration_s": len(frames) / 20,
        "road_id": context["road_id"], "device_id": context["device_id"],
        "stationary_frames": stationary, "fully_left_governed_frames": left,
        "fully_right_governed_frames": right, "centerline_straddling_frames": straddling,
        "outside_governed_extent_frames": out_of_extent,
        "legal_result": None,
        "unresolved": ["official notice authority and conformity", "one-way legal designation",
                       "legal standing or parking purpose", "Native source and actual sign pixels"],
    }


def measure_original(raw_poses: bytes, raw_frame_map: bytes,
                     raw_context: bytes, raw_opendrive: bytes) -> dict:
    """Join retained Native traces; never fill absent legal authority from a fixture."""
    context = json.loads(raw_context)
    require(context.get('map_source_sha256') == sha(raw_opendrive), 'OpenDRIVE source hash mismatch')
    poses = [json.loads(line) for line in raw_poses.splitlines() if line.strip()]
    frame_map = [json.loads(line) for line in raw_frame_map.splitlines() if line.strip()]
    require(len(poses) == len(frame_map), 'original frame map length mismatch')
    require(bool(poses), 'original vehicle trace missing')
    for pose, mapping in zip(poses, frame_map):
        require(pose['video_frame'] == mapping['video_frame'] and
                pose['native_frame'] == mapping['native_frame'] and
                pose['camera_native_frames'] == mapping['camera_native_frames'] and
                abs(pose['time_s'] - mapping['time_s']) < 1e-8,
                'original frame map join mismatch')
    vehicle_id = poses[0].get('vehicle_id')
    packet = {'assignment_id': ASSIGNMENT, 'source_kind': 'native_saved_sample',
              'vehicle_id': vehicle_id, 'frames': poses}
    result = measure(json.dumps(packet, sort_keys=True, separators=(',', ':')).encode(), raw_context)
    result['original_pose_sha256'] = sha(raw_poses)
    result['original_frame_map_sha256'] = sha(raw_frame_map)
    result['original_opendrive_sha256'] = sha(raw_opendrive)
    return result
