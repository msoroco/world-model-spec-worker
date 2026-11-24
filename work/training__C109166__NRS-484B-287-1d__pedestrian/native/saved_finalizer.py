"""Saved-only diagnostic finalizer for the diagonal crossing source pair.

Raw pedestrian poses, map geometry and device states are separately hashed and
joined. An official-device or NRS 484B.290 finding requires independent review.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
RATE = 20
DEVICE = "c109166-planned-diagonal-head"


def _read(path: Path, expected: str) -> bytes:
    if not path.is_file():
        raise ValueError("required saved source missing: " + path.name)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("saved source hash mismatch: " + path.name)
    return raw


def _rows(raw: bytes, name: str) -> list[dict]:
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if len(rows) != FRAMES:
        raise ValueError("full 600-frame " + name + " source required")
    for index, row in enumerate(rows):
        if row.get("frame") != index or row.get("time_s") != index / RATE:
            raise ValueError(name + " frame/time join failed")
    return rows


def _inside(point: list[float], bounds: list[float]) -> bool:
    return bounds[0] <= point[0] <= bounds[2] and bounds[1] <= point[1] <= bounds[3]


def finalize(folder: Path, hashes: dict[str, str], case: str) -> dict:
    if case not in ("probe_01", "probe_02"):
        raise ValueError("unknown exact case")
    required = ("pedestrian.jsonl", "device.jsonl", "map.json")
    if set(hashes) != set(required):
        raise ValueError("all three saved source hashes required")
    raw = {name: _read(folder / name, hashes[name]) for name in required}
    map_source = json.loads(raw["map.json"])
    if (map_source.get("source_kind") != "synthetic_native_sample" or
            map_source.get("intersection_bounds_xy_m") != [-5, -5, 5, 5] or
            map_source.get("device_id") != DEVICE or
            map_source.get("official_status") != "unverified" or
            map_source.get("exception_484b290") != "unresolved"):
        raise ValueError("map/device legal context changed or missing")
    pedestrians = _rows(raw["pedestrian.jsonl"], "pedestrian")
    devices = _rows(raw["device.jsonl"], "device")
    centers = []
    for index, (person, device) in enumerate(zip(pedestrians, devices)):
        center = person.get("pedestrian_xy_m")
        footprint = person.get("footprint_xy_m")
        if (person.get("source_kind") != "synthetic_native_sample" or
                not isinstance(center, list) or len(center) != 2 or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in center) or
                not isinstance(footprint, list) or len(footprint) != 4 or
                any(not isinstance(point, list) or len(point) != 2 or
                    any(type(v) not in (int, float) or not math.isfinite(v) for v in point)
                    for point in footprint)):
            raise ValueError("original-shape pedestrian source missing")
        if any(abs(sum(point[k] for point in footprint) / 4 - center[k]) > 1e-8
               for k in (0, 1)):
            raise ValueError("pedestrian footprint/center disagreement")
        if (device.get("device_id") != DEVICE or
                device.get("official_status") != "unverified" or
                device.get("display_code") not in ("diagonal_walk_requested", "no_diagonal_permission") or
                device.get("source_kind") != "synthetic_native_sample"):
            raise ValueError("device source missing or authority overstated")
        if index and math.dist(center, centers[-1]) > 0.08:
            raise ValueError("pedestrian motion discontinuity")
        centers.append(center)
    if centers[100] != [-6, -6] or centers[340] != [6, 6]:
        raise ValueError("diagonal endpoint source changed")
    inside = [i for i, center in enumerate(centers)
              if _inside(center, map_source["intersection_bounds_xy_m"])]
    if not inside or min(inside) >= 340 or max(inside) <= 100:
        raise ValueError("intersection crossing not observed")
    expected = "diagonal_walk_requested" if case == "probe_01" else "no_diagonal_permission"
    if any(devices[i]["display_code"] != expected for i in inside):
        raise ValueError("device state differs during observed crossing")
    distance = sum(math.dist(a, b) for a, b in zip(centers, centers[1:]))
    return {"format": "c109166-saved-diagonal-diagnostic-v1", "case": case,
            "source_sha256": hashes, "frames": FRAMES, "duration_s": FRAMES / RATE,
            "path_length_m": round(distance, 6),
            "intersection_entry_frame": min(inside), "intersection_exit_frame": max(inside),
            "device_display_during_crossing": expected,
            "official_device_verified": False, "exception_484b290_resolved": False,
            "physical_crossing_claimed": False, "legal_verdict": None}
