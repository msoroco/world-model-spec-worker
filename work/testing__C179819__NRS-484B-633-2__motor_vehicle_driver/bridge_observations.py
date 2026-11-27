"""Source-bound bridge approach and crossing observations for NRS 484B.633(2).

This module reports physical measurements and document provenance. It does not
decide whether a structure or a driver's speed is legally safe.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re


FEET_PER_METRE = 3.280839895013123
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _finite(value, label):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise ValueError(f"finite {label} required")
    return float(value)


def read_bound_json(path: Path, expected_sha256: str) -> dict:
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"original source missing: {path.name}")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError(f"original source hash differs: {path.name}")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError(f"original source object required: {path.name}")
    return value


def verify_site_bundle(path: Path, expected_sha256: str, case_id: str) -> dict:
    """Verify external administrative and surveyed sources, without executing them."""
    path = Path(path)
    if path.is_symlink():
        raise ValueError("original bridge dossier cannot be a symlink")
    path = path.resolve()
    dossier = read_bound_json(path, expected_sha256)
    validate_site(dossier, expected_case=case_id)
    refs = [dossier["maximum_declaration_source"], dossier["stationing_source"]]
    refs.extend(dossier["authority"].values())
    for sign in dossier["signs"].values():
        refs.extend((sign["erected_source"], sign["maintained_source"]))
    for ref in refs:
        if not isinstance(ref, dict) or not isinstance(ref.get("path"), str) or not re.fullmatch(
                r"[0-9a-f]{64}", str(ref.get("sha256", ""))):
            raise ValueError("source-hashed original administrative/survey record required")
        source = path.parent / ref["path"]
        if source.is_symlink() or not source.is_file() or path.parent not in source.resolve().parents:
            raise ValueError("original bridge dossier source missing or outside bundle")
        if hashlib.sha256(source.read_bytes()).hexdigest() != ref["sha256"]:
            raise ValueError("original bridge dossier source hash differs")
    return dossier


def validate_site(dossier: dict, *, expected_case: str | None = None) -> dict:
    """Require a reviewed original dossier for both approaches and Department act.

    Stations are original road-centreline metres increasing from end A to end B.
    End A's sign is before A in the positive direction; end B's sign is beyond B
    in the negative direction. The 100-foot measure is reported, not rounded into
    a fabricated placement tolerance.
    """
    if not isinstance(dossier, dict):
        raise ValueError("original site dossier required")
    if dossier.get("format") != "worker-bridge-site-v1":
        raise ValueError("bridge site dossier format differs")
    if expected_case is not None and dossier.get("case_id") != expected_case:
        raise ValueError("bridge site case identity differs")
    if dossier.get("structure_kind") not in ("bridge", "other_elevated_structure"):
        raise ValueError("bridge or other elevated structure source required")
    a = _finite(dossier.get("end_a_station_m"), "end A station")
    b = _finite(dossier.get("end_b_station_m"), "end B station")
    if b - a < 10:
        raise ValueError("ordered distinct elevated structure ends required")
    signs = dossier.get("signs")
    if not isinstance(signs, dict) or set(signs) != {"end_a", "end_b"}:
        raise ValueError("suitable original signs before both ends required")
    for end, expected_side in (("end_a", -1), ("end_b", 1)):
        sign = signs[end]
        if not isinstance(sign, dict):
            raise ValueError(f"original {end} sign source required")
        station = _finite(sign.get("station_m"), f"{end} sign station")
        structure_end = a if end == "end_a" else b
        if (station - structure_end) * expected_side <= 0:
            raise ValueError(f"original {end} sign lies on wrong approach")
        if not sign.get("erected_source") or not sign.get("maintained_source"):
            raise ValueError(f"original {end} sign erection/maintenance sources required")
        if sign.get("face_direction") != ("toward_b" if end == "end_a" else "toward_a"):
            raise ValueError(f"original {end} sign face direction differs")
    maximum = _finite(dossier.get("declared_maximum_mph"), "declared maximum mph")
    if maximum <= 0 or not dossier.get("maximum_declaration_source"):
        raise ValueError("source-backed positive Department maximum required")
    authority = dossier.get("authority")
    required = ("chapter_408_source", "highway_source", "investigation_source",
                "finding_source", "department_decision_source", "sign_causation_source")
    if not isinstance(authority, dict) or any(not authority.get(key) for key in required):
        raise ValueError("Department chapter 408 investigation/decision chronology sources required")
    if not dossier.get("map_opendrive_sha256") or not dossier.get("stationing_source"):
        raise ValueError("original mapped highway stationing and OpenDRIVE hash required")
    offsets = {
        "end_a": (a - float(signs["end_a"]["station_m"])) * FEET_PER_METRE,
        "end_b": (float(signs["end_b"]["station_m"]) - b) * FEET_PER_METRE,
    }
    return {"end_a_station_m": a, "end_b_station_m": b,
            "sign_offsets_ft": offsets, "declared_maximum_mph": maximum,
            "structure_kind": dossier["structure_kind"]}


def measure_crossing(dossier: dict, rows: list[dict], case_id: str, *, expected_frames: int = 900) -> dict:
    site = validate_site(dossier, expected_case=case_id)
    if len(rows) != expected_frames:
        raise ValueError(f"{expected_frames} original 20 Hz frames required")
    direction = dossier.get("travel_direction")
    if direction not in ("a_to_b", "b_to_a"):
        raise ValueError("original approach direction required")
    a, b = site["end_a_station_m"], site["end_b_station_m"]
    speeds = []
    first_station = last_station = None
    crossing_frames = []
    last_original_frame = None
    first_time_s = None
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("index") != index:
            raise ValueError("contiguous original frame indices required")
        frame = row.get("original_frame")
        if not isinstance(frame, int) or (last_original_frame is not None and frame != last_original_frame + 1):
            raise ValueError("contiguous original simulator frames required")
        last_original_frame = frame
        time_s = _finite(row.get("time_s"), "original time")
        if first_time_s is None:
            first_time_s = time_s
        if abs(time_s - first_time_s - index / 20) > 0.01:
            raise ValueError("original 20 Hz time join differs")
        station = _finite(row.get("ego_station_m"), "ego station")
        speed = _finite(row.get("ego_speed_mps"), "ego speed")
        if speed < 0:
            raise ValueError("negative original speed")
        if row.get("ego_actor_id") != dossier.get("ego_actor_id"):
            raise ValueError("original ego actor identity differs")
        if first_station is None:
            first_station = station
        last_station = station
        if a <= station <= b:
            crossing_frames.append(frame)
            speeds.append(speed * 2.2369362920544)
    if not crossing_frames:
        raise ValueError("no original frame on elevated structure")
    if direction == "a_to_b" and not (first_station < a and last_station > b):
        raise ValueError("original A-to-B approach and exit incomplete")
    if direction == "b_to_a" and not (first_station > b and last_station < a):
        raise ValueError("original B-to-A approach and exit incomplete")
    return {"case_id": case_id, "direction": direction,
            "structure_kind": site["structure_kind"],
            "sign_offsets_ft": site["sign_offsets_ft"],
            "declared_maximum_mph": site["declared_maximum_mph"],
            "observed_crossing_speed_mph": {"minimum": min(speeds), "maximum": max(speeds),
                                            "samples": len(speeds)},
            "crossing_original_frames": [crossing_frames[0], crossing_frames[-1]],
            "original_frame_count": len(rows),
            "speed_relative_to_declared_maximum": "measured_only_no_legal_verdict",
            "sign_placement_judgment": "unresolved",
            "structure_safety_judgment": "unresolved",
            "physical_completion": "requires_independent_original_review"}
