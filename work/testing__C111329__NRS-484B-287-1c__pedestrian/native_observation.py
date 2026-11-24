"""Original 20 Hz walker and device observations for a selected exact case.

The caller supplies the real CARLA world, walker, and a device reader. The
reader must return original device identity and operating state after each
world tick. This module does not decide legal official status or exceptions.
"""

from __future__ import annotations

import hashlib
import json
import math
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

from PIL import Image

from site_geometry import assess_site

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CAMERA_DIMENSIONS = {"overview": (1920, 1080), "approach": (1280, 720),
                     "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def _image_bytes(reader, frame: int, dimensions: tuple[int, int]) -> bytes:
    sample = reader(frame)
    if not isinstance(sample, dict) or sample.get("frame") != frame:
        raise ValueError("original camera frame identity mismatch")
    payload = sample.get("png_bytes")
    if not isinstance(payload, bytes) or not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("original camera PNG missing")
    with Image.open(BytesIO(payload)) as image:
        image.verify()
    with Image.open(BytesIO(payload)) as image:
        if image.format != "PNG" or image.size != dimensions:
            raise ValueError("original camera dimensions mismatch")
        image.load()
    return payload


def _canonical(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def capture_observation(world, walker, packet: dict, case_id: str, output: str | Path,
                        read_device, *, ticks: int = 900, camera_readers=None,
                        camera_dimensions=None) -> dict:
    """Write original observations; ``ticks`` is injectable for CPU fixtures."""
    site = assess_site(packet, require_operating=False)
    if not isinstance(case_id, str) or not case_id:
        raise ValueError("exact case ID required")
    if not isinstance(ticks, int) or ticks < 2:
        raise ValueError("at least two Native ticks required")
    if not callable(read_device):
        raise ValueError("device reader required")
    expected = set(site["device_ids"])
    packet_sha = hashlib.sha256(_canonical(packet)).hexdigest()
    frames = []
    path = Path(output)
    if path.exists():
        raise ValueError("original observation output exists")
    if camera_readers is not None and set(camera_readers) != set(CAMERAS):
        raise ValueError("four named camera readers required")
    dimensions = camera_dimensions or CAMERA_DIMENSIONS
    if set(dimensions) != set(CAMERAS):
        raise ValueError("four named camera dimensions required")
    media_paths = {name: path.parent / (path.stem + "." + name + ".png.zip")
                   for name in CAMERAS} if camera_readers is not None else {}
    if any(p.exists() for p in media_paths.values()):
        raise ValueError("original camera output exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    archives = {name: ZipFile(p, "w", compression=ZIP_STORED)
                for name, p in media_paths.items()}
    previous_frame = None
    previous_time = None
    try:
      for _ in range(ticks):
        tick_frame = int(world.tick())
        snapshot = world.get_snapshot()
        frame = int(snapshot.frame)
        time_s = float(snapshot.timestamp.elapsed_seconds)
        if frame != tick_frame or (previous_frame is not None and frame != previous_frame + 1):
            raise ValueError("Native frame discontinuity")
        if not math.isfinite(time_s) or (previous_time is not None and not 0.049 <= time_s - previous_time <= 0.051):
            raise ValueError("Native 20 Hz clock discontinuity")
        position = walker.get_location()
        xyz = [float(position.x), float(position.y), float(position.z)]
        if not all(math.isfinite(v) for v in xyz):
            raise ValueError("invalid original walker position")
        readings = [read_device(device_id) for device_id in sorted(expected)]
        if {r.get("device_id") for r in readings} != expected or len(readings) != len(expected):
            raise ValueError("device identity readback mismatch")
        for r in readings:
            if not isinstance(r.get("actor_id"), int) or r["actor_id"] < 0:
                raise ValueError("device actor identity missing")
            if not isinstance(r.get("state"), str) or not r["state"]:
                raise ValueError("device state readback missing")
            if type(r.get("is_operating")) is not bool:
                raise ValueError("device operation readback missing")
        row = {"frame": frame, "time_s": time_s, "walker_xyz_m": xyz,
               "devices": readings}
        if camera_readers is not None:
            row["camera_frames"] = {}
            for name in CAMERAS:
                payload = _image_bytes(camera_readers[name], frame, tuple(dimensions[name]))
                member = f"{frame:08d}.png"
                archives[name].writestr(member, payload)
                row["camera_frames"][name] = {"member": member,
                                              "sha256": hashlib.sha256(payload).hexdigest()}
        frames.append(row)
        previous_frame, previous_time = frame, time_s
    finally:
        for archive in archives.values():
            archive.close()
        if len(frames) != ticks:
            for media_path in media_paths.values():
                media_path.unlink(missing_ok=True)
    document = {"format": "original-pedestrian-site-observation", "case_id": case_id,
                "packet_sha256": packet_sha, "source_sha256": site["source_sha256"],
                "frame_count": ticks, "frames": frames,
                "camera_sources": {name: {"path": str(media_path),
                    "sha256": hashlib.sha256(media_path.read_bytes()).hexdigest(),
                    "frame_count": ticks, "dimensions": list(dimensions[name])}
                    for name, media_path in media_paths.items()}}
    path.write_bytes(_canonical(document))
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "frame_count": ticks, "case_id": case_id,
            "camera_capture_complete": camera_readers is not None}


def analyze_saved(packet: dict, receipt: dict, *, expected_case_id: str,
                  required_frames: int = 900) -> dict:
    """Reject stale/partial original observations and summarize measured motion."""
    site = assess_site(packet, require_operating=False)
    path = Path(receipt["path"])
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != receipt.get("sha256"):
        raise ValueError("original observation hash mismatch")
    document = json.loads(data)
    if document.get("format") != "original-pedestrian-site-observation" or document.get("case_id") != expected_case_id or receipt.get("case_id") != expected_case_id:
        raise ValueError("exact observation case mismatch")
    if document.get("packet_sha256") != hashlib.sha256(_canonical(packet)).hexdigest() or document.get("source_sha256") != site["source_sha256"]:
        raise ValueError("site source binding mismatch")
    frames = document.get("frames")
    if (not isinstance(frames, list) or len(frames) != required_frames or
            document.get("frame_count") != required_frames or receipt.get("frame_count") != required_frames):
        raise ValueError("original observation frame count mismatch")
    expected = set(site["device_ids"])
    positions = []
    all_operating = True
    previous_frame = previous_time = None
    for sample in frames:
        frame, time_s = sample["frame"], sample["time_s"]
        if not isinstance(frame, int) or (previous_frame is not None and frame != previous_frame + 1):
            raise ValueError("saved frame discontinuity")
        if not isinstance(time_s, (int, float)) or not math.isfinite(time_s) or (previous_time is not None and not 0.049 <= time_s - previous_time <= 0.051):
            raise ValueError("saved 20 Hz clock discontinuity")
        xyz = sample["walker_xyz_m"]
        if len(xyz) != 3 or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in xyz):
            raise ValueError("saved walker position missing")
        readings = sample["devices"]
        if len(readings) != len(expected) or {r["device_id"] for r in readings} != expected:
            raise ValueError("saved device identity mismatch")
        if any(not isinstance(r.get("actor_id"), int) or r["actor_id"] < 0 or not isinstance(r.get("state"), str) or not r["state"] or type(r.get("is_operating")) is not bool for r in readings):
            raise ValueError("saved device readback missing")
        all_operating &= all(r["is_operating"] for r in readings)
        positions.append(xyz)
        previous_frame, previous_time = frame, time_s
    def crossing_segments(bank):
        a, b = bank
        def cross(p, q, r):
            return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        return [i for i, (p, q) in enumerate(zip(positions, positions[1:]))
                if cross(a, b, p) * cross(a, b, q) < 0 and
                cross(p, q, a) * cross(p, q, b) < 0]
    crossings = [crossing_segments(bank) for bank in packet["highway_banks"]]
    if not all(crossings):
        raise ValueError("walker did not cross both observed highway banks")
    first, last = min(min(indices) for indices in crossings), max(max(indices) for indices in crossings) + 1
    during_crossing = all(r["is_operating"] for sample in frames[first:last + 1]
                          for r in sample["devices"])
    return {"case_id": expected_case_id, "frame_count": required_frames,
            "original_observation_sha256": receipt["sha256"],
            "crossed_both_highway_banks": True, "both_devices_operating_all_frames": all_operating,
            "both_devices_operating_during_crossing": during_crossing,
            "observed_crossing_frame_range": [frames[first]["frame"], frames[last]["frame"]],
            "observed_crossing_time_s": [frames[first]["time_s"], frames[last]["time_s"]],
            "marked_crosswalk_present_in_survey": site["marked_crosswalk_present"],
            "legal_adjacency": "undetermined", "legal_official_status": "undetermined",
            "nrs_484b_290_exception": "undetermined"}
