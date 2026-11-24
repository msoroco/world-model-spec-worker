"""Source-bound left-turn motion and capture lifecycle CPU checks.

These checks assess original body samples. They do not decide right of way,
actual pixel visibility, or whether a requested controller state occurred.
"""

import hashlib
import json
import math
from pathlib import Path

from left_turn_measurements import body_occupancy


EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lifecycle(events, *, encoder_exit_codes, restoration_verified):
    if events != EVENTS:
        raise ValueError("saved processing requires closed Native ownership")
    if not restoration_verified or any(code != 0 for code in encoder_exit_codes.values()):
        raise ValueError("encoders and world restoration must finish before release")
    return {"events": list(events), "exit_code": 0}


def assess(trace_path, map_path):
    trace_path, map_path = Path(trace_path), Path(map_path)
    sources = {str(path): _sha(path) for path in (trace_path, map_path) if path.is_file()}
    base = {"provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "physical_acceptance_claimed": False}
    if not trace_path.is_file() or not map_path.is_file():
        return {**base, "maneuver_completed": False, "realized_observables": {},
                "physical_checks": {"maneuver": {"status": "unverified",
                    "method": "missing original trace or map", "sources": sources}}}
    packet = json.loads(map_path.read_text(encoding="utf-8"))
    polygon = packet.get("intersection_polygon")
    if not polygon or not packet.get("source_ref"):
        raise ValueError("source-bound intersection polygon required")
    rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    if len(rows) < 3:
        raise ValueError("three original body samples required")
    frames = [row["frame"] for row in rows]
    if frames != list(range(frames[0], frames[0] + len(rows))):
        raise ValueError("noncontiguous original body frames")
    if any(abs(rows[i]["time_s"] - rows[i-1]["time_s"] - 0.05) > 0.002
           for i in range(1, len(rows))):
        raise ValueError("original body samples are not 20 Hz")
    occupancies = [body_occupancy(row["ego_vertices"], polygon) for row in rows]
    centers = [(sum(v[0] for v in row["ego_vertices"]) / 8,
                sum(v[1] for v in row["ego_vertices"]) / 8) for row in rows]
    distance = sum(math.dist(a, b) for a, b in zip(centers, centers[1:]))
    inside = next((i for i, occ in enumerate(occupancies) if occ["full_body_inside"]), None)
    cleared = inside is not None and any(
        rows[i]["ego_turn_committed"] and not occupancies[i]["any_vertex_inside"]
        for i in range(inside + 1, len(rows)))
    met = bool(cleared and distance > 3.0)
    check = {"status": "met" if met else "not_met",
             "method": "original full-body intersection entry, committed exit, and sampled path",
             "sources": sources,
             "observed": {"full_body_entry_frame": None if inside is None else frames[inside],
                          "sampled_path_m": distance, "committed_exit": bool(cleared)}}
    return {**base, "maneuver_completed": met,
            "realized_observables": {"sampled_path_m": distance} if met else {},
            "physical_checks": {"maneuver": check}}
