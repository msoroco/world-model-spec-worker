"""Join sealed original motion, relation and frame-map sources after capture."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from right_side_measurement import ASSIGNMENT, measure_packet


def _read(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def finalize(attempt: Path, case_id: str) -> dict:
    attempt = Path(attempt)
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("exact selected case required")
    paths = {name: attempt / name for name in
             ("original-motion.json", "original-relation.json", "original-frame-map.json")}
    for name, path in paths.items():
        if not path.is_file():
            raise ValueError("Missing required original source: " + name)
    motion, motion_sha = _read(paths["original-motion.json"])
    relation, relation_sha = _read(paths["original-relation.json"])
    frame_map, frame_map_sha = _read(paths["original-frame-map.json"])
    if (motion.get("assignment_id") != ASSIGNMENT or motion.get("case_id") != case_id or
            relation.get("case_id") != case_id or frame_map.get("case_id") != case_id or
            relation.get("source_kind") != "original_native_relation" or
            frame_map.get("source_kind") != "original_native_frame_map" or
            motion.get("original_frame_map_sha256") != frame_map_sha):
        raise ValueError("sealed original case/frame-map source mismatch")
    rows = motion.get("frames")
    relations = relation.get("samples")
    frames = frame_map.get("frames")
    if (not all(isinstance(x, list) and len(x) == 900 for x in (rows, relations, frames))):
        raise ValueError("original 900-frame source history required")
    joined = []
    for index, (row, reading, frame) in enumerate(zip(rows, relations, frames)):
        if (row.get("frame") != index or reading.get("frame") != index or
                frame.get("frame") != index or row.get("time_s") != reading.get("time_s") or
                row.get("time_s") != frame.get("time_s") or
                row.get("follower_actor_id") != reading.get("follower_actor_id") or
                type(reading.get("immediately_behind")) is not bool):
            raise ValueError("original frame, time or follower join differs")
        if "follower_immediately_behind_readback" in row:
            raise ValueError("unsealed inline follower relation forbidden")
        if set(frame.get("camera_frames", {})) != {
                "overview", "approach", "reference_corner", "driver_reference"}:
            raise ValueError("original four-view camera frame map incomplete")
        if len(set(frame["camera_frames"].values())) != 1:
            raise ValueError("original four-view camera frames not synchronized")
        joined.append({**row,
                       "follower_immediately_behind_readback": reading["immediately_behind"]})
    measured = measure_packet({**motion, "frames": joined},
        {"motion_path": str(paths["original-motion.json"]), "motion_sha256": motion_sha,
         "relation_path": str(paths["original-relation.json"]), "relation_sha256": relation_sha,
         "frame_map_path": str(paths["original-frame-map.json"]), "frame_map_sha256": frame_map_sha})
    measured["format"] = "c323986-original-source-join-v1"
    measured["original_frame_count"] = 900
    return measured
