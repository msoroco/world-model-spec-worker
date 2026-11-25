"""Source-bound, original-frame Native acquisition for the crossing cases.

The caller supplies a CARLA adapter at execution time. This module imports no
simulator and does not turn a diagnostic adapter into physical evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from native_crossing import construct_walker, crossing_plan, digest, point

CAMERAS = ("front", "rear", "left", "right")


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _sealed(value: str, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} must be a SHA256 hex digest")
    return value


def acquire(adapter, *, site: dict, site_sha256: str, case_id: str,
            route_kind: str, authorization: bool, blueprint_id: str,
            frames: int = 900, fps: int = 20,
            capture_root: Path | None = None) -> dict:
    """Record original source readbacks while commanding one exact walker route.

    ``adapter`` supplies ``tick``, ``walker_xy``, ``walker_id``,
    ``read_devices``, ``camera_frames``, ``stop_walker`` and the construction
    adapter methods. Device readbacks must include every inventoried device and
    bind each device to its independently inspected official/instruction source.
    """
    _sealed(site_sha256, "site_sha256")
    if digest(site) != site_sha256:
        raise ValueError("site source hash mismatch")
    if not case_id or frames < 3 or fps != 20:
        raise ValueError("invalid exact-case capture contract")
    plan = crossing_plan(site, route_kind, authorization)
    devices = site["devices"]
    if not isinstance(devices, list) or not devices:
        raise ValueError("device inventory required")
    by_id = {d.get("id"): d for d in devices}
    if None in by_id or len(by_id) != len(devices):
        raise ValueError("unique inventoried device IDs required")
    for device in devices:
        if not device.get("official_source") or not device.get("instruction_source"):
            raise ValueError("official device and instruction source required")
    diagnostic = getattr(adapter, 'is_diagnostic', None)
    if not isinstance(diagnostic, bool):
        raise ValueError('adapter diagnostic provenance missing')
    actor, plan = construct_walker(adapter, site, route_kind, authorization, blueprint_id)
    rows = []
    if capture_root is not None:
        capture_root.mkdir(parents=True, exist_ok=True)
    original_id = adapter.walker_id(actor)
    last_frame = None
    last_time = None
    try:
        for _ in range(frames):
            snapshot = adapter.tick()
            frame = snapshot.get("original_frame")
            time_s = snapshot.get("elapsed_seconds")
            if not isinstance(frame, int) or isinstance(frame, bool) or not isinstance(time_s, (int, float)) or not math.isfinite(time_s):
                raise ValueError("Native original frame/time readback missing")
            if last_frame is not None and (frame != last_frame + 1 or abs((time_s - last_time) - 1 / fps) > 0.002):
                raise ValueError("Native original frame/time discontinuity")
            walker_id = adapter.walker_id(actor)
            if walker_id != original_id:
                raise ValueError("Native walker identity discontinuity")
            xy = point(adapter.walker_xy(actor))
            actor_state = None if diagnostic else adapter.actor_state(actor)
            if not diagnostic:
                vertices = actor_state.get('body_vertices_m') if isinstance(actor_state, dict) else None
                velocity = actor_state.get('velocity_mps') if isinstance(actor_state, dict) else None
                if (actor_state.get('actor_id') != original_id or
                        not str(actor_state.get('blueprint', '')).startswith('walker.pedestrian.') or
                        not isinstance(vertices, list) or len(vertices) < 4 or
                        any(len(v) != 3 or not all(math.isfinite(float(x)) for x in v) for v in vertices) or
                        not isinstance(velocity, list) or len(velocity) != 3 or
                        not all(math.isfinite(float(x)) for x in velocity) or
                        not math.isfinite(float(actor_state.get('heading_deg')))):
                    raise ValueError('Native full pedestrian body and velocity readback missing')
            raw_devices = adapter.read_devices()
            if not isinstance(raw_devices, list) or {d.get("id") for d in raw_devices} != set(by_id) or len(raw_devices) != len(by_id):
                raise ValueError("Native device inventory readback incomplete")
            device_rows = []
            for d in raw_devices:
                source = by_id[d["id"]]
                if d.get("official_source") != source["official_source"] or d.get("instruction_source") != source["instruction_source"]:
                    raise ValueError("Native device provenance changed")
                if d.get("pedestrian_governance") != source.get("pedestrian_governance") or d.get("state") not in {"permissive", "prohibitive", "unknown"}:
                    raise ValueError("Native device governance/state invalid")
                device_rows.append({"id": d["id"], "official_source": d["official_source"],
                                    "instruction_source": d["instruction_source"],
                                    "pedestrian_governance": d["pedestrian_governance"],
                                    "state": d["state"], "source_sha256": _sha(d)})
            cameras = adapter.camera_frames()
            if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS) or any(cameras[name] != frame for name in CAMERAS):
                raise ValueError("Native four-camera frame readback mismatch")
            png_hashes = {}
            if capture_root is not None:
                for name in CAMERAS:
                    raw = adapter.camera_png(name, frame)
                    if not isinstance(raw, bytes) or not raw.startswith(b"\x89PNG\r\n\x1a\n"):
                        raise ValueError("Native original camera PNG bytes missing")
                    path = capture_root / name / f"{frame:06d}.png"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(raw)
                    png_hashes[name] = hashlib.sha256(raw).hexdigest()
            rows.append({"original_frame": frame, "elapsed_seconds": time_s,
                         "walker_id": walker_id, "walker_center_xy": xy,
                         "actor_state": actor_state,
                         "devices": sorted(device_rows, key=lambda d: d["id"]),
                         "camera_frames": {name: cameras[name] for name in CAMERAS},
                         "camera_png_sha256": png_hashes})
            last_frame, last_time = frame, time_s
    finally:
        adapter.stop_walker(actor)
        adapter.destroy_actor(actor)
    if not any(math.dist(row["walker_center_xy"], plan["end"]) <= 1.5 for row in rows):
        raise ValueError("Native walker endpoint never observed")
    return {"format": "crossing-native-acquisition-v1", "case_id": case_id,
            "site_sha256": site_sha256, "plan_sha256": _sha(plan),
            "device_inventory_sha256": plan["device_inventory_sha256"],
            "fps": fps, "frame_count": frames, "walker_id": original_id,
            "original_frame_start": rows[0]["original_frame"],
            "original_frame_end": rows[-1]["original_frame"],
            "rows": rows, "rows_sha256": _sha(rows), "diagnostic": diagnostic}


def save(path: Path, packet: dict) -> str:
    """Persist the acquisition receipt without rewriting source frame data."""
    if packet.get("format") != "crossing-native-acquisition-v1" or packet.get("rows_sha256") != _sha(packet.get("rows")):
        raise ValueError("unsealed Native acquisition packet")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(packet, sort_keys=True, separators=(",", ":")) + "\n"
    path.write_text(payload, encoding="utf-8")
    return hashlib.sha256(payload.encode()).hexdigest()
