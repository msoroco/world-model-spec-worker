"""Join independently sealed immediate-follower readback to original motion.

The relation source must itself be a reviewed Native observation. This join
does not decide whether the driver's slow speed legally impeded traffic.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from right_lane_measurement import ASSIGNMENT, measure_packet


def _read(path, expected_sha):
    path = Path(path)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError("original follower source hash mismatch")
    return json.loads(raw)


def finalize(trace_path, trace_sha, relation_path, relation_sha, case_id):
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("exact right-lane case required")
    trace = _read(trace_path, trace_sha)
    relation = _read(relation_path, relation_sha)
    if (trace.get("assignment_id") != ASSIGNMENT or trace.get("case_id") != case_id or
            relation.get("case_id") != case_id or
            relation.get("source_kind") != "original_native_relation" or
            not relation.get("relation_basis_source")):
        raise ValueError("original exact follower relation source required")
    frames, readings = trace.get("frames"), relation.get("samples")
    if not isinstance(frames, list) or not isinstance(readings, list) or len(frames) != len(readings) or len(frames) != 900:
        raise ValueError("original 900-frame follower join required")
    first = frames[0].get("frame")
    if type(first) is not int or [row.get("frame") for row in frames] != list(range(first, first + 900)):
        raise ValueError("original frame sequence differs")
    joined = []
    for frame, reading in zip(frames, readings):
        if (reading.get("frame") != frame["frame"] or
                reading.get("time_s") != frame.get("time_s") or
                reading.get("follower_actor_id") != frame.get("follower_actor_id") or
                type(reading.get("immediately_behind")) is not bool):
            raise ValueError("original follower identity/frame/time join differs")
        if "follower_immediately_behind_readback" in frame:
            raise ValueError("unsealed inline follower relation forbidden")
        joined.append({**frame,
                       "follower_immediately_behind_readback": reading["immediately_behind"]})
    packet = {**trace, "frames": joined,
              "follower_relation_source_sha256": relation_sha}
    result = measure_packet(packet, {"trace_sha256": trace_sha,
                                     "relation_sha256": relation_sha})
    result["format"] = "c147344-original-follower-relation-join-v1"
    result["case_id"] = case_id
    result["original_frame_count"] = 900
    result["relation_basis_source"] = relation["relation_basis_source"]
    result["legal_impediment_and_pass_necessity"] = "unresolved"
    return result
