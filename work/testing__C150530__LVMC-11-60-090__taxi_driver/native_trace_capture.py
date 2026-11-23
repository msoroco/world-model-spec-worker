"""Original 20 Hz road/pose acquisition for the taxi first-turn measurement.

The caller owns world ticking, cameras, actor cleanup and world restoration.
Closing seals only complete contiguous samples joined to reviewed context.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from reviewed_context import validate as validate_context
from taxi_native_motion import validate_native_map
from turn_trace_finalizer import _samples, ASSIGNMENT, RATE_HZ


class TraceCapture:
    def __init__(self, attempt_root: Path, case: str, world, actor,
                 map_path: Path, layout_path: Path, context_packet: Path):
        self.root = Path(attempt_root).resolve()
        if not self.root.is_dir() or "runtime" in self.root.parts:
            raise ValueError("original trace attempt root is absent or inside frozen runtime")
        self.trace = self.root / "original-trace.jsonl"
        self.seal = self.root / "original-trace-seal.json"
        if self.trace.exists() or self.seal.exists():
            raise ValueError("original trace attempt already used")
        self.case = case
        self.world = world
        self.actor = actor
        self.map_path = Path(map_path)
        self.layout_path = Path(layout_path)
        self.context_packet = Path(context_packet)
        if not self.context_packet.resolve().is_relative_to(self.root):
            raise ValueError("reviewed context packet must be retained in attempt")
        self.map_sha = validate_native_map(world, self.map_path.read_bytes(), case)
        validate_context(json.loads(self.context_packet.read_text()), self.root,
                         self.map_path, self.layout_path)
        self.handle = self.trace.open("x")
        self.closed = False

    def record(self) -> dict:
        if self.closed:
            raise ValueError("original trace writer is closed")
        snapshot = self.world.get_snapshot()
        transform = self.actor.get_transform()
        waypoint = self.world.get_map().get_waypoint(transform.location,
                                                      project_to_road=True)
        if waypoint is None:
            raise ValueError("Native waypoint unavailable for taxi pose")
        row = {"frame": int(snapshot.frame),
               "time_s": float(snapshot.timestamp.elapsed_seconds),
               "x_m": float(transform.location.x), "y_m": float(transform.location.y),
               "position_m": [float(transform.location.x), float(transform.location.y),
                              float(transform.location.z)],
               "yaw_deg": float(transform.rotation.yaw),
               "road_id": int(waypoint.road_id), "lane_id": int(waypoint.lane_id)}
        self.handle.write(json.dumps(row, separators=(",", ":")) + "\n")
        self.handle.flush()
        return row

    def close(self, *, completed: bool) -> dict | None:
        if self.closed:
            raise ValueError("original trace writer already closed")
        self.closed = True
        self.handle.close()
        if not completed:
            return None
        rows = _samples(self.trace)
        validate_context(json.loads(self.context_packet.read_text()), self.root,
                         self.map_path, self.layout_path)
        if validate_native_map(self.world, self.map_path.read_bytes(), self.case) != self.map_sha:
            raise ValueError("Native map changed before trace seal")
        receipt = {"format": "c150530-original-trace-seal-v1",
                   "case_id": ASSIGNMENT + "__" + self.case,
                   "rate_hz": RATE_HZ,
                   "trace_sha256": hashlib.sha256(self.trace.read_bytes()).hexdigest(),
                   "context_packet_sha256": hashlib.sha256(self.context_packet.read_bytes()).hexdigest(),
                   "map_sha256": self.map_sha,
                   "frame_count": len(rows),
                   "first_frame": rows[0]["frame"],
                   "last_frame": rows[-1]["frame"]}
        self.seal.write_text(json.dumps(receipt, indent=2) + "\n")
        return receipt
