"""Retain original crosswalk actor observations with same-tick camera identities.

The caller owns the CARLA world, actor setup and camera encoding. This adapter
requires a complete 20 Hz capture and writes source files for saved measurement;
it makes no claim about realized crossing geometry, visibility or legality.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from crosswalk_measurements import ASSIGNMENT_ID


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
FRAME_COUNT = 900


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _center(value):
    if not isinstance(value, list) or len(value) != 2 or not all(_finite(v) for v in value):
        raise ValueError("original two-dimensional center required")
    return value


def _vertices(value):
    if not isinstance(value, list) or len(value) != 8 or any(
        not isinstance(vertex, list) or len(vertex) != 3 or not all(_finite(v) for v in vertex)
        for vertex in value
    ):
        raise ValueError("eight original world-space body vertices required")
    return value


class NativeCrosswalkRecorder:
    def __init__(self, *, case_id: str, context: dict, actor_ids: dict):
        if not isinstance(case_id, str) or not case_id.startswith(ASSIGNMENT_ID + "__"):
            raise ValueError("exact case identity required")
        if not isinstance(context, dict) or context.get("case_id") != case_id:
            raise ValueError("original case context required")
        if not isinstance(actor_ids, dict) or set(actor_ids) != {"ego", "lead", "pedestrian"}:
            raise ValueError("three original actor identities required")
        if any(not isinstance(value, str) or not value.strip() for value in actor_ids.values()):
            raise ValueError("nonempty original actor identities required")
        if len(set(actor_ids.values())) != 3:
            raise ValueError("distinct original actor identities required")
        if any(context.get(key + "_identity") != actor_ids[name] for key, name in
               (("ego_vehicle", "ego"), ("lead_vehicle", "lead"), ("pedestrian", "pedestrian"))):
            raise ValueError("context and original actor identities differ")
        self.case_id = case_id
        self.context = context
        self.actor_ids = dict(actor_ids)
        self.rows = []
        self.frame_map = []

    def append(self, *, world_frame: int, actors: dict, camera_frames: dict) -> dict:
        index = len(self.rows)
        if index >= FRAME_COUNT:
            raise ValueError("capture exceeds planned Native duration")
        if type(world_frame) is not int or world_frame < 0:
            raise ValueError("original integer world frame required")
        if self.rows and world_frame != self.rows[-1]["frame"] + 1:
            raise ValueError("original Native ticks must be consecutive")
        if not isinstance(camera_frames, dict) or set(camera_frames) != set(CAMERAS):
            raise ValueError("four named original camera frames required")
        if any(getattr(camera_frames[name], "frame", None) != world_frame for name in CAMERAS):
            raise ValueError("camera image frame differs from Native world tick")
        if not isinstance(actors, dict) or set(actors) != set(self.actor_ids):
            raise ValueError("all original actors required at every tick")
        for role, observation in actors.items():
            if not isinstance(observation, dict) or observation.get("actor_id") != self.actor_ids[role]:
                raise ValueError("original actor identity differs")
            _center(observation.get("center"))
            if not isinstance(observation.get("source_ref"), str) or str(world_frame) not in observation["source_ref"]:
                raise ValueError("actor source must identify original Native frame")
        for role in ("ego", "lead"):
            _vertices(actors[role].get("vertices"))
            speed = actors[role].get("speed_mps")
            if not _finite(speed) or speed < 0:
                raise ValueError("finite nonnegative original vehicle speed required")
        time_s = index / 20
        row = {"frame": world_frame, "time_s": time_s,
               "ego_center": actors["ego"]["center"], "lead_center": actors["lead"]["center"],
               "pedestrian_center": actors["pedestrian"]["center"],
               "ego_vertices": actors["ego"]["vertices"], "lead_vertices": actors["lead"]["vertices"],
               "ego_speed_mps": actors["ego"]["speed_mps"],
               "lead_speed_mps": actors["lead"]["speed_mps"],
               "actor_sources": {role: actors[role]["source_ref"] for role in self.actor_ids}}
        mapping = {"video_frame": index, "carla_frame": world_frame, "time_s": time_s}
        self.rows.append(row)
        self.frame_map.append(mapping)
        return mapping

    def write(self, directory: str | Path) -> dict:
        if len(self.rows) != FRAME_COUNT:
            raise ValueError("complete 900-frame Native capture required")
        root = Path(directory)
        if not root.is_dir() or any((root / name).exists() for name in
                                    ("context.json", "trace.jsonl", "frame-map.jsonl", "receipt.json")):
            raise ValueError("fresh capture destination required")
        context_raw = (json.dumps(self.context, sort_keys=True, allow_nan=False) + "\n").encode()
        trace_raw = "".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in self.rows).encode()
        frame_map_raw = "".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in self.frame_map).encode()
        receipt = {"assignment_id": ASSIGNMENT_ID, "case_id": self.case_id,
                   "diagnostic_fixture": False, "fps": 20, "frame_count": FRAME_COUNT,
                   "context_sha256": hashlib.sha256(context_raw).hexdigest(),
                   "trace_sha256": hashlib.sha256(trace_raw).hexdigest(),
                   "frame_map_sha256": hashlib.sha256(frame_map_raw).hexdigest(),
                   "camera_identity_status": "same_tick_only_saved_media_decode_required",
                   "physical_acceptance_claimed": False}
        for name, raw in (("context.json", context_raw), ("trace.jsonl", trace_raw),
                          ("frame-map.jsonl", frame_map_raw),
                          ("receipt.json", (json.dumps(receipt, sort_keys=True) + "\n").encode())):
            (root / name).write_bytes(raw)
        return receipt
