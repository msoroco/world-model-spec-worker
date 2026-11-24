"""Synthetic source-shape checks; no Native or legal outcome is claimed."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from one_way_saved_measure import ASSIGNMENT, CAMERAS, measure, measure_original


def enc(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def sample(side: str):
    y = {"left": 1.5, "right": -1.5, "center": 0.0, "beyond": 1.5}[side]
    x = 31 if side == "beyond" else 20
    fake_sha = hashlib.sha256(b"synthetic source for diagnostic only").hexdigest()
    context = {
        "assignment_id": ASSIGNMENT, "source_kind": "synthetic_native_sample",
        "map_source_sha256": fake_sha, "one_way_designation_source_sha256": fake_sha,
        "street_boundary_source_sha256": fake_sha, "device_authority_source_sha256": fake_sha,
        "device_content_source_sha256": fake_sha, "device_erection_source_sha256": fake_sha,
        "road_id": "road-1", "roadway_is_one_way": True,
        "device_id": "notice-1", "device_erected": True, "device_official": True,
        "notice_prohibits_left_standing_or_parking": True,
        "device_governs_road_id": "road-1", "centerline_origin_xy_m": [0, 0],
        "permitted_direction_xy": [1, 0], "governed_longitudinal_extent_m": [0, 30],
        "street_half_width_m": 3.5,
    }
    frames = []
    for i in range(600):
        frames.append({
            "video_frame": i, "native_frame": i + 101, "time_s": i / 20,
            "vehicle_id": "ego", "speed_mps": 0 if 200 <= i < 400 else 3,
            "camera_native_frames": {name: i + 101 for name in CAMERAS},
            "footprint_corners_xy_m": [[x-2, y-.7], [x+2, y-.7],
                                        [x+2, y+.7], [x-2, y+.7]],
        })
    packet = {"assignment_id": ASSIGNMENT, "source_kind": "synthetic_native_sample",
              "vehicle_id": "ego", "frames": frames}
    return packet, context


def reject(packet, context, message):
    try:
        measure(enc(packet), enc(context))
    except ValueError as exc:
        if str(exc) != message:
            raise
        return
    raise RuntimeError("invalid saved source accepted: " + message)


def lines(rows):
    return ("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n").encode()


def reject_original(poses, mapping, context, road, message):
    try:
        measure_original(poses, mapping, context, road)
    except ValueError as exc:
        if str(exc) != message:
            raise
        return
    raise RuntimeError("invalid original source accepted: " + message)


def main():
    root = Path(__file__).resolve().parents[2]
    source = root / "inputs" / ASSIGNMENT
    source_hashes = {name: hashlib.sha256((source / name).read_bytes()).hexdigest()
                     for name in ("assignment.json", "witnesses.json")}
    law = json.loads((source / "assignment.json").read_text())["law"]["text"]
    if "official traffic-control devices" not in law or "left-hand side of a one-way street" not in law:
        raise ValueError("frozen law text changed")
    results = {}
    for side, expected in (("left", "fully_left_governed_frames"),
                           ("right", "fully_right_governed_frames"),
                           ("center", "centerline_straddling_frames"),
                           ("beyond", "outside_governed_extent_frames")):
        packet, context = sample(side)
        row = measure(enc(packet), enc(context))
        if row[expected] != list(range(200, 400)) or row["legal_result"] is not None:
            raise RuntimeError("side/extent diagnostic mismatch: " + side)
        results[side] = row["frames_sha256"]
    packet, context = sample("left")
    failures = [
        ("missing_official_authority", lambda p, c: c.__setitem__("device_authority_source_sha256", ""),
         "device_authority_source_sha256 missing"),
        ("not_one_way", lambda p, c: c.__setitem__("roadway_is_one_way", False),
         "one-way roadway source missing"),
        ("missing_notice", lambda p, c: c.__setitem__("notice_prohibits_left_standing_or_parking", False),
         "left-side prohibition notice missing"),
        ("wrong_road", lambda p, c: c.__setitem__("device_governs_road_id", "road-2"),
         "device does not govern roadway"),
        ("changed_vehicle", lambda p, c: p["frames"][300].__setitem__("vehicle_id", "other"),
         "vehicle identity changed"),
        ("missing_camera", lambda p, c: p["frames"][300]["camera_native_frames"].pop("sign_face"),
         "four-camera frame join missing"),
        ("missing_frame", lambda p, c: p["frames"].pop(300),
         "recording shorter than 30 seconds"),
        ("wrong_direction", lambda p, c: c.__setitem__("permitted_direction_xy", [0, 0]),
         "permitted direction must be unit length"),
    ]
    for _, change, message in failures:
        bad_packet, bad_context = copy.deepcopy(packet), copy.deepcopy(context)
        change(bad_packet, bad_context)
        reject(bad_packet, bad_context, message)
    packet, context = sample("left")
    context['source_kind'] = 'native_saved_sample'
    road = b'<OpenDRIVE source="synthetic-shape-check" />'
    context['map_source_sha256'] = hashlib.sha256(road).hexdigest()
    original_poses = lines(packet['frames'])
    original_map = lines([{'video_frame': row['video_frame'], 'native_frame': row['native_frame'],
                           'time_s': row['time_s'], 'camera_native_frames': row['camera_native_frames']}
                          for row in packet['frames']])
    original = measure_original(original_poses, original_map, enc(context), road)
    if original['fully_left_governed_frames'] != list(range(200, 400)):
        raise RuntimeError('original saved-source join failed')
    reject_original(original_poses, original_map, enc(context), b'wrong map',
                    'OpenDRIVE source hash mismatch')
    bad_map = [json.loads(line) for line in original_map.splitlines()]
    bad_map[300]['native_frame'] += 1
    reject_original(original_poses, lines(bad_map), enc(context), road,
                    'original frame map join mismatch')
    print(json.dumps({"passed": True, "source_hashes": source_hashes,
                      "positive_packet_hashes": results,
                      "negative_checks": [name for name, _, _ in failures] +
                                         ['changed_opendrive', 'broken_original_frame_map'],
                      "original_saved_join_sha256": original['original_pose_sha256'],
                      "source_kind": "synthetic_native_sample",
                      "physical_acceptance_claimed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
