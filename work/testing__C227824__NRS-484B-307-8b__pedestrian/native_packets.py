"""Original C227824 walker/signal/camera packet writer, without CARLA import.

The caller runs one synchronized CARLA tick, waits for each camera image, and
supplies that snapshot here. This file writes source packets only; it never
seals capture, decodes video, or claims physical acceptance.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from native_signal import sample as sample_signal
from saved_entry import CAMERAS, PACKETS


def _finite(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("nonfinite original body coordinate")
    return number


def _body(actor, scene, frame, time_s):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    if len(vertices) != 8:
        raise ValueError("original walker needs eight world-space body vertices")
    xyz = [(_finite(v.x), _finite(v.y), _finite(v.z)) for v in vertices]
    xs, ys = [v[0] for v in xyz], [v[1] for v in xyz]
    if max(xs) - min(xs) < .1 or max(ys) - min(ys) < .1:
        raise ValueError("degenerate original walker footprint")
    # A conservative XY envelope includes every original walker body vertex.
    polygon = [[min(xs), min(ys)], [max(xs), min(ys)],
               [max(xs), max(ys)], [min(xs), max(ys)]]
    return {"case_id": scene["case_id"], "frame": frame, "time_s": time_s,
            "actor_id": int(actor.id), "body_polygon_xy_m": polygon,
            "body_z_min_m": min(v[2] for v in xyz),
            "body_z_max_m": max(v[2] for v in xyz),
            "source_kind": "original_native_world_vertices_envelope"}


def sample_tick(scene, walker, head, others, snapshot, camera_frames):
    """Reject any stale camera image before producing five joined source rows."""
    frame = snapshot.frame
    time_s = snapshot.timestamp.elapsed_seconds
    if type(frame) is not int or frame < 0 or not isinstance(time_s, (int, float)) or not math.isfinite(time_s):
        raise ValueError("invalid original world snapshot")
    if not isinstance(camera_frames, dict) or set(camera_frames) != set(CAMERAS):
        raise ValueError("four original camera frames required")
    joins = {}
    for name in CAMERAS:
        image = camera_frames[name]
        if getattr(image, "frame", None) != frame:
            raise ValueError("stale or missing original camera frame: " + name)
        joins[name] = {"frame": frame, "width": int(image.width),
                       "height": int(image.height)}
        if joins[name]["width"] <= 0 or joins[name]["height"] <= 0:
            raise ValueError("invalid original camera dimensions")
    body = _body(walker, scene, frame, float(time_s))
    signal, device = sample_signal(head, others, scene, frame=frame, time_s=time_s)
    common = {"case_id": scene["case_id"], "frame": frame, "time_s": float(time_s)}
    return {"walker-body-history.jsonl": body,
            "signal-history.jsonl": signal,
            "device-history.jsonl": device,
            "video_frames.jsonl": {"video_frame": None, "carla_frame": frame,
                                   "time_s": float(time_s)},
            "camera-frame-joins.jsonl": {**common, "cameras": joins}}


class PacketWriter:
    """Append exact synchronized packet groups to a private attempt directory."""

    def __init__(self, attempt):
        self.root = Path(attempt).resolve()
        workspace = Path(__file__).resolve().parents[2]
        private = (workspace / ".runtime-work").resolve()
        if not self.root.is_dir() or not self.root.is_relative_to(private):
            raise ValueError("Native attempt must exist under .runtime-work")
        self.streams = {}
        for name in PACKETS:
            if (self.root / name).exists():
                raise ValueError("original packet file already exists: " + name)
        try:
            for name in PACKETS:
                self.streams[name] = (self.root / name).open("x", buffering=1)
        except BaseException:
            self.close()
            raise
        self.count = 0
        self.last_frame = -1
        self.last_time = -math.inf

    def append(self, packets):
        if set(packets) != set(PACKETS):
            raise ValueError("incomplete original packet group")
        body = packets["walker-body-history.jsonl"]
        frame, time_s = body["frame"], body["time_s"]
        if frame <= self.last_frame or time_s <= self.last_time:
            raise ValueError("original packet frames must be strictly increasing")
        for name in PACKETS:
            row = packets[name]
            if name == "video_frames.jsonl":
                if row.get("carla_frame") != frame or row.get("time_s") != time_s:
                    raise ValueError("original frame-map join differs")
            elif row.get("frame") != frame or row.get("time_s") != time_s or row.get("case_id") != body.get("case_id"):
                raise ValueError("original packet time/case join differs")
        packets["video_frames.jsonl"]["video_frame"] = self.count
        encoded = {name: json.dumps(packets[name], allow_nan=False) + "\n" for name in PACKETS}
        for name in PACKETS:
            self.streams[name].write(encoded[name])
        self.count += 1
        self.last_frame, self.last_time = frame, time_s

    def close(self):
        for stream in self.streams.values():
            stream.close()
        self.streams = {}


def source_hashes(attempt):
    """Hash completed source bytes after encoder exit; no seal claim is made."""
    root = Path(attempt).resolve()
    names = ("scene.json", *PACKETS, *(camera + ".mkv" for camera in CAMERAS))
    hashes = {}
    for name in names:
        path = root / name
        if not path.is_file() or not path.stat().st_size:
            raise ValueError("missing completed original source: " + name)
        hashes[name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return hashes
