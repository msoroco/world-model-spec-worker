"""Seal a distinct third Native actor alongside the exact reciprocal attempt.

The adapter returns the ordinary four capture values plus a same-tick later
opponent sample. This wrapper never infers the later actor from the first one.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from left_turn_measurements import body_occupancy, opposing_approach
from native_acquisition import capture
from reciprocal_saved import ASSIGNMENT, SOURCE


class ThreeActorAdapter:
    def __init__(self, source, polygon):
        self.source = source
        self.polygon = polygon
        self.rows = []
        self.identities = None

    def source_attestation(self):
        return self.source.source_attestation()

    def tick(self):
        values = self.source.tick()
        if not isinstance(values, tuple) or len(values) != 5:
            raise ValueError("three-actor Native tick required")
        frame, time_s, primary, cameras, later = values
        if not isinstance(primary, dict) or not isinstance(later, dict):
            raise ValueError("original third actor sample missing")
        keys = ("later_opponent_actor_id", "later_opponent_vertices",
                "later_opponent_heading", "later_opponent_speed_mps",
                "later_opponent_braking", "later_opponent_driver_control_source")
        if any(key not in later for key in keys):
            raise ValueError("original third actor field missing")
        identities = (primary.get("ego_actor_id"), primary.get("opponent_actor_id"),
                      later["later_opponent_actor_id"])
        if (any(type(actor) is not int for actor in identities) or
                len(set(identities)) != 3 or
                (self.identities is not None and identities != self.identities)):
            raise ValueError("three distinct stable Native actor identities required")
        self.identities = identities
        speed = later["later_opponent_speed_mps"]
        if (type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0 or
                type(later["later_opponent_braking"]) is not bool or
                not later["later_opponent_driver_control_source"]):
            raise ValueError("original third actor control readback missing")
        body_occupancy(later["later_opponent_vertices"], self.polygon)
        if opposing_approach(primary["ego_heading"], later["later_opponent_heading"]) > -0.5:
            raise ValueError("later Native actor is not opposite-direction traffic")
        self.rows.append({"frame": frame, "time_s": time_s,
                          **{key: later[key] for key in keys}})
        return frame, time_s, primary, cameras


def capture_reciprocal(*, adapter, case_id, map_path, output, frame_count=900):
    if case_id not in (ASSIGNMENT + "__reciprocal_yield",
                       ASSIGNMENT + "__reciprocal_no_yield"):
        raise ValueError("exact reciprocal case required")
    packet = json.loads(Path(map_path).read_text(encoding="utf-8"))
    joined = ThreeActorAdapter(adapter, packet["intersection_polygon"])
    paths = capture(adapter=joined, case_id=case_id, map_path=map_path,
                    output=output, frame_count=frame_count)
    root = Path(output)
    primary = [json.loads(line) for line in paths["trace_path"].read_text().splitlines()]
    if (len(joined.rows) != frame_count or
            [(row["frame"], row["time_s"]) for row in joined.rows] !=
            [(row["frame"], row["time_s"]) for row in primary]):
        raise ValueError("third actor original frame/time join differs")
    source = root / SOURCE
    raw = "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
                  for row in joined.rows).encode()
    source.write_bytes(raw)
    receipt_path = paths["receipt_path"]
    receipt = json.loads(receipt_path.read_text())
    receipt["later_opponent_trace_sha256"] = hashlib.sha256(raw).hexdigest()
    receipt_path.write_text(json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n")
    return {**paths, "later_opponent_path": source}
