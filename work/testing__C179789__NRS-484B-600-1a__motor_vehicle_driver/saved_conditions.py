"""Measure basic-speed scene conditions from sealed original Native samples.

These engineering measurements leave reasonable/proper speed unresolved.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


FIELDS = ("ego_speed_mps", "leader_gap_m", "highway_width_m", "surface_wetness",
          "precipitation_strength", "fog_density", "tire_friction")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _number(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return float(value)


def measure(attempt: Path, case_id: str) -> dict:
    """Require sealed raw 20 Hz samples and retain the complete history."""
    attempt = Path(attempt)
    seal = json.loads((attempt / "original-conditions-seal.json").read_bytes())
    if seal.get("format") != "c179789-conditions-v1" or seal.get("case_id") != case_id:
        raise ValueError("original conditions identity differs")
    raw_path = attempt / "original-conditions.jsonl"
    data = raw_path.read_bytes()
    if _sha(data) != seal.get("sha256"):
        raise ValueError("original conditions source hash differs")
    rows = [json.loads(line) for line in data.splitlines() if line]
    if len(rows) < 3 or len(rows) != seal.get("frame_count"):
        raise ValueError("original conditions frame count differs")
    previous = None
    source_ids = None
    for row in rows:
        frame = row.get("frame")
        if isinstance(frame, bool) or not isinstance(frame, int) or frame < 0:
            raise ValueError("original frame must be a nonnegative integer")
        time = _number(row.get("time_s"), "time_s")
        if previous and (frame != previous[0] + 1 or not .049 <= time - previous[1] <= .051):
            raise ValueError("original frames and times must be contiguous at 20 Hz")
        previous = (frame, time)
        for field in FIELDS:
            value = _number(row.get(field), field)
            if value < 0:
                raise ValueError(f"{field} cannot be negative")
        if row["surface_wetness"] > 1 or row["precipitation_strength"] > 100 or row["fog_density"] > 100:
            raise ValueError("Native weather or wetness range differs")
        if not isinstance(row.get("source_frame"), int) or row["source_frame"] != frame:
            raise ValueError("condition source frame join differs")
        ids = row.get("source_ids")
        if not isinstance(ids, dict) or not all(ids.get(name) is not None for name in
             ("ego_actor_id", "leader_actor_id", "road_id", "lane_id", "opendrive_sha256")):
            raise ValueError("original actor and OpenDRIVE source IDs are missing")
        if source_ids is None:
            source_ids = ids
        elif ids != source_ids:
            raise ValueError("original actor or OpenDRIVE source changed during capture")
    if (rows[0]["frame"], rows[-1]["frame"]) != (seal.get("first_frame"), seal.get("last_frame")):
        raise ValueError("original frame endpoints differ")
    return {"case_id": case_id, "source": {"path": raw_path.name, "sha256": _sha(data)},
            "first_frame": rows[0]["frame"], "last_frame": rows[-1]["frame"],
            "sample_count": len(rows), "source_ids": source_ids, "full_history": rows,
            "provenance_kind": "synthetic_fixture" if seal.get("diagnostic_fixture") else "native_api_capture",
            "diagnostic_fixture": bool(seal.get("diagnostic_fixture")),
            "summary": {field: {"first": rows[0][field],
                                "minimum": min(row[field] for row in rows),
                                "maximum": max(row[field] for row in rows),
                                "mean": sum(row[field] for row in rows) / len(rows)}
                        for field in FIELDS},
            "legal_judgment": "unresolved", "physical_acceptance_claimed": False}


def seal(attempt: Path, case_id: str, rows: list[dict], *, diagnostic_fixture: bool = True) -> dict:
    """Write one original source once; the caller owns source provenance."""
    attempt = Path(attempt)
    if "runtime" in attempt.resolve().parts:
        raise ValueError("source output cannot be under frozen runtime")
    if len(rows) < 3:
        raise ValueError("original condition capture requires three frames")
    attempt.mkdir(parents=True, exist_ok=True)
    raw_path = attempt / "original-conditions.jsonl"
    seal_path = attempt / "original-conditions-seal.json"
    if raw_path.exists() or seal_path.exists():
        raise ValueError("original attempt already used")
    data = b"".join((json.dumps(row, sort_keys=True) + "\n").encode() for row in rows)
    raw_path.write_bytes(data)
    result = {"format": "c179789-conditions-v1", "case_id": case_id,
              "sha256": _sha(data), "frame_count": len(rows),
              "first_frame": rows[0]["frame"], "last_frame": rows[-1]["frame"],
              "diagnostic_fixture": diagnostic_fixture}
    seal_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
