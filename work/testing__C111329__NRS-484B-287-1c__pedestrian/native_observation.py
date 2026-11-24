"""Original 20 Hz walker and device observations for a selected exact case.

The caller supplies the real CARLA world, walker, and a device reader. The
reader must return original device identity and operating state after each
world tick. This module does not decide legal official status or exceptions.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from site_geometry import assess_site


def _canonical(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def capture_observation(world, walker, packet: dict, case_id: str, output: str | Path,
                        read_device, *, ticks: int = 900) -> dict:
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
    previous_frame = None
    previous_time = None
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
        frames.append({"frame": frame, "time_s": time_s, "walker_xyz_m": xyz,
                       "devices": readings})
        previous_frame, previous_time = frame, time_s
    document = {"format": "original-pedestrian-site-observation", "case_id": case_id,
                "packet_sha256": packet_sha, "source_sha256": site["source_sha256"],
                "frame_count": ticks, "frames": frames}
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical(document))
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "frame_count": ticks, "case_id": case_id}


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
