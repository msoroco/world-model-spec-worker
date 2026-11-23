"""Seal original Native bicycle motion and supplied contemporaneous context.

The caller must supply source-verified context from the actual episode. This
writer never converts an authored condition or controller target into evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from speed_measurement import REQUIRED_CONDITIONS, REQUIRED_CONTEXT, measure


def _bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def seal_original_acquisition(root: Path, case_id: str, route_samples: list,
                              context: dict, *, context_source: dict) -> dict:
    """Write once, hash every source, then independently read back all joins."""
    root = Path(root)
    if root.exists() and any(root.iterdir()):
        raise ValueError("refusing to overwrite original Native acquisition")
    if not route_samples or len(route_samples) < 20:
        raise ValueError("incomplete original bicycle route")
    if context.get("case_id") != case_id or context.get("source_kind") != "original_local_native_capture":
        raise ValueError("context is not an original Native case source")
    if any(k not in context for k in REQUIRED_CONTEXT):
        raise ValueError("original context lacks required source")
    if context_source.get("path") is None or context_source.get("sha256") is None:
        raise ValueError("original context source reference missing")
    source_path = Path(context_source["path"])
    if not source_path.is_file() or hashlib.sha256(source_path.read_bytes()).hexdigest() != context_source["sha256"]:
        raise ValueError("original context source hash mismatch")
    if json.loads(source_path.read_bytes()) != context:
        raise ValueError("supplied context differs from original source packet")
    frames = []
    motions = []
    previous = None
    for row in route_samples:
        frame = row.get("frame_id")
        stamp = row.get("time_s")
        velocity = row.get("velocity_mps")
        x, y = row.get("x_m"), row.get("y_m")
        if (type(frame) is not int or type(stamp) not in (int, float) or
                not math.isfinite(stamp) or not isinstance(velocity, list) or
                len(velocity) != 3 or any(type(v) not in (int, float) or
                not math.isfinite(v) for v in velocity) or
                type(x) not in (int, float) or type(y) not in (int, float) or
                not math.isfinite(x) or not math.isfinite(y)):
            raise ValueError("invalid original bicycle motion")
        if previous and (frame != previous[0] + 1 or abs(stamp - previous[1] - .05) > .005):
            raise ValueError("original bicycle frame/time continuity failure")
        frames.append({"frame": frame, "time_s": stamp})
        motions.append({"frame": frame, "time_s": stamp, "velocity_mps": velocity,
                        "x_m": row["x_m"], "y_m": row["y_m"]})
        previous = (frame, stamp)
    conditions = context.get("samples")
    if not isinstance(conditions, list) or len(conditions) != len(frames):
        raise ValueError("original condition history incomplete")
    for index, (condition, frame) in enumerate(zip(conditions, frames)):
        if condition.get("frame") != frame["frame"] or condition.get("time_s") != frame["time_s"]:
            raise ValueError("original condition frame/time join mismatch at " + str(index))
        if any(key not in condition for key in REQUIRED_CONDITIONS):
            raise ValueError("original condition fields incomplete")
    payloads = {
        "frame-map.json": {"frames": frames},
        "bicycle-motion.json": {"case_id": case_id, "samples": motions},
        "context.json": context,
    }
    root.mkdir(parents=True, exist_ok=True)
    inventory = {"case_id": case_id, "source_kind": "original_native", "sources": {},
                 "context_source": context_source, "legal_prudence": "unresolved"}
    for name, payload in payloads.items():
        raw = _bytes(payload)
        (root / name).write_bytes(raw)
        key = {"frame-map.json": "frame_map", "bicycle-motion.json": "bicycle_motion",
               "context.json": "context"}[name]
        inventory["sources"][key] = {"path": name, "sha256": hashlib.sha256(raw).hexdigest()}
    measure(root, inventory, case_id)
    (root / "inventory.json").write_bytes(_bytes(inventory))
    return inventory
