"""Close one restored Native capture for the pinned saved-processing protocol."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from camera_sources import audit_camera_sources
from prepare_derived_media import prepare as prepare_derived_media
from source_tick_capture import verify_seal


def close_capture(attempt: Path, release: dict) -> dict:
    root = Path(attempt)
    if release.get("source_kind") != "original_capture" or release.get("world_restore", {}).get("restored") is not True:
        raise ValueError("original Native capture and verified world restore required")
    if (root / "capture-seal.json").exists():
        raise ValueError("capture already sealed")
    packet = verify_seal(root)
    audit_camera_sources(root, diagnostic_fixture=False)
    samples = packet["samples"]
    originals = [json.loads(line) for line in
                 (root / "nearest-view-original-ticks.jsonl").read_text().splitlines()]
    if len(samples) != 900 or len(originals) != len(samples):
        raise ValueError("original 900-frame capture required")
    identity = json.loads((root / "capture-identity.json").read_text())
    construction_hash = hashlib.sha256((root / "construction.json").read_bytes()).hexdigest()
    if identity.get("construction_sha256") != construction_hash:
        raise ValueError("capture construction differs from selected Native revision")
    traces = []
    mappings = []
    for index, (row, raw) in enumerate(zip(samples, originals)):
        vertices = raw["ego"]["body_vertices_xy_m"]
        velocity = raw["ego"]["velocity_xy_mps"]
        center = [sum(point[axis] for point in vertices) / len(vertices) for axis in (0, 1)]
        traces.append({"frame": row["frame"], "time_s": row["time_s"],
                       "position_m": [center[0], center[1], 0.0],
                       "position": {"x": center[0], "y": center[1], "z": 0.0},
                       "heading_deg": math.degrees(math.atan2(velocity[1], velocity[0])),
                       "speed_mps": row["ego_speed_mps"],
                       "speed_mph": row["ego_speed_mps"] / .44704,
                       "velocity_mps": [velocity[0], velocity[1], 0.0],
                       "control": {}})
        mappings.append({"video_frame": index, "carla_frame": row["frame"],
                         "native_frame": row["frame"],
                         "time_s": row["time_s"]})
    (root / "trace.jsonl").write_text("".join(json.dumps(row) + "\n" for row in traces))
    (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in mappings))
    prepare_derived_media(root, diagnostic_fixture=False)
    (root / "acquisition-provenance.json").write_text(json.dumps({
        "format": "worker-acquisition-provenance", "provenance_kind": "native",
        "diagnostic_fixture": False, "case_id": identity["case_id"],
        "capture_identity_sha256": hashlib.sha256((root / "capture-identity.json").read_bytes()).hexdigest(),
        "physical_acceptance_claimed": False}, indent=2) + "\n")
    from worker_exchange.native_output import seal_capture
    return seal_capture(root, frames=len(samples), restoration=release["world_restore"],
                        errors=[], encoder_exit_codes={},
                        context={"case_id": identity["case_id"],
                                 "source_kind": "original_capture", "legal_status": "unresolved"})
