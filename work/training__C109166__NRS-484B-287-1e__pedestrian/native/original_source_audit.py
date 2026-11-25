"""Independent saved-only structural audit of an original diagonal attempt.

This checks original-source integrity, not whether a device is legally official
or whether the pedestrian complied with it.
"""
import hashlib
import json
import math
from pathlib import Path

from native_request import FRAMES, validate_source_frames, verify_authority_sources


def _hashed_rows(folder, source, expected_hash):
    path = folder / source
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
        raise ValueError("missing or stale original source: " + source)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _point(value):
    return isinstance(value, list) and len(value) == 2 and all(
        type(x) in (int, float) and math.isfinite(x) for x in value)


def audit(folder, source_hashes, authority_receipt):
    folder = Path(folder)
    required = {"video_frames.jsonl", "pedestrian-original.jsonl",
                "device-original.jsonl", "camera-sources.jsonl"}
    if set(source_hashes) != required:
        raise ValueError("all original source hashes required")
    data = {name: _hashed_rows(folder, name, source_hashes[name]) for name in required}
    mapping = data["video_frames.jsonl"]
    people = data["pedestrian-original.jsonl"]
    devices = data["device-original.jsonl"]
    cameras = data["camera-sources.jsonl"]
    if any(len(data[name]) != FRAMES for name in required - {"camera-sources.jsonl"}):
        raise ValueError("full original frame histories required")
    frame_ids = []
    times = []
    for index, (frame_row, person, device) in enumerate(zip(mapping, people, devices)):
        frame = frame_row.get("native_frame")
        time = frame_row.get("time_s")
        if (frame_row.get("video_frame") != index or type(frame) is not int or
                type(time) not in (int, float) or not math.isfinite(time) or
                (index and (frame <= frame_ids[-1] or time <= times[-1]))):
            raise ValueError("original frame map identity/time invalid")
        frame_ids.append(frame)
        times.append(time)
        if (person.get("native_frame") != frame or person.get("time_s") != time or
                type(person.get("walker_id")) is not int or
                not _point(person.get("center_xy_m")) or
                not isinstance(person.get("footprint_xy_m"), list) or
                len(person["footprint_xy_m"]) != 4 or
                any(not _point(point) for point in person["footprint_xy_m"])):
            raise ValueError("original full pedestrian body/frame join invalid")
        if (device.get("native_frame") != frame or device.get("time_s") != time or
                device.get("device_id") != "c109166-diagonal-crossing-head" or
                device.get("source_kind") != "native_device_readback" or
                device.get("displayed_instruction") not in
                ("diagonal_walk", "diagonal_dont_walk") or not device.get("source_ref")):
            raise ValueError("original governing device readback/frame join invalid")
    if times[-1] - times[0] < 29.9:
        raise ValueError("original capture duration below 30-second plan")
    camera_summary = validate_source_frames(cameras, mapping)
    authority = verify_authority_sources(folder, authority_receipt)
    entry_candidates = [i for i, person in enumerate(people)
                        if person.get("road_entry_proxy_observed") is True and
                        person.get("road_boundary_review_pending") is True]
    if not entry_candidates:
        raise ValueError("original road entry proxy observation missing")
    first = entry_candidates[0]
    return {"format": "c109166-original-source-structural-audit-v1",
            "source_sha256": dict(source_hashes), "authority_source_sha256": authority["source_sha256"],
            "frame_count": FRAMES, "first_entry_video_frame": first,
            "first_entry_native_frame": frame_ids[first],
            "road_boundary_review_pending": True,
            "first_entry_device_instruction": devices[first]["displayed_instruction"],
            "duration_s": times[-1] - times[0], "camera_source_summary": camera_summary,
            "official_status_verified": False, "diagonal_authorization_verified": False,
            "physical_completion_verified": False, "actual_pixels_reviewed": False,
            "legal_verdict": None}
