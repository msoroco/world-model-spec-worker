"""Retain four independent 900-frame Native packets for saved finalization."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from native_construction import ASSIGNMENT, lane_change_route


def _offset_m(location, source_points):
    """Signed displacement from the nearest reviewed source-lane segment."""
    best = None
    for a, b in zip(source_points, source_points[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length_sq = dx * dx + dy * dy
        if length_sq <= 0:
            continue
        u = max(0.0, min(1.0, ((location.x - a[0]) * dx +
                               (location.y - a[1]) * dy) / length_sq))
        cx, cy = a[0] + u * dx, a[1] + u * dy
        distance_sq = (location.x - cx) ** 2 + (location.y - cy) ** 2
        signed = (dx * (location.y - cy) - dy * (location.x - cx)) / math.sqrt(length_sq)
        if best is None or distance_sq < best[0]:
            best = (distance_sq, signed)
    if best is None:
        raise ValueError("reviewed source-lane geometry has no segment")
    return best[1]


class NativeReadbacks:
    """The check reader must be a separate original driver-input source.

    It returns a source ID, original Native frame and elapsed time, and a boolean
    event. A controller request or observed traffic state cannot be used in place
    of this driver-input readback.
    """

    def __init__(self, packet: dict, case_id: str, actor, carla, check_reader):
        if not case_id.startswith(ASSIGNMENT + "__"):
            raise ValueError("exact lane-change case required")
        if check_reader is None:
            raise ValueError("independent original driver-check input reader required")
        lane_change_route(packet)
        self.packet, self.case_id, self.actor, self.carla = packet, case_id, actor, carla
        self.check_reader = check_reader
        self.source_points = packet["lanes"]["source"]["centerline_world_xyz_m"]
        self.rows = {name: [] for name in ("frame_map", "ego_pose", "native_signal", "driver_check")}
        self.check_source = None

    def sample(self, frame: int, time_s: float):
        if (type(frame) is not int or type(time_s) not in (int, float) or
                not math.isfinite(time_s) or len(self.rows["frame_map"]) >= 900):
            raise ValueError("original Native 900-frame clock required")
        if self.rows["frame_map"] and (frame != self.rows["frame_map"][-1]["frame"] + 1 or
                                         time_s <= self.rows["frame_map"][-1]["t_s"]):
            raise ValueError("original Native frame/time sequence differs")
        observed = self.check_reader(frame, time_s)
        if not isinstance(observed, dict) or observed.get("source_kind") != "original_driver_input" or not observed.get("source_id"):
            raise ValueError("independent original driver-check source required")
        if observed.get("frame") != frame or observed.get("t_s") != time_s or type(observed.get("observed")) is not bool:
            raise ValueError("independent driver-check frame/time readback differs")
        if self.check_source is None:
            self.check_source = observed["source_id"]
        elif self.check_source != observed["source_id"]:
            raise ValueError("driver-check input source changed during capture")
        transform = self.actor.get_transform()
        pos = transform.location
        state = int(self.actor.get_light_state())
        left = bool(state & int(self.carla.VehicleLightState.LeftBlinker))
        right = bool(state & int(self.carla.VehicleLightState.RightBlinker))
        common = {"frame": frame, "t_s": time_s}
        self.rows["frame_map"].append(common)
        self.rows["ego_pose"].append({**common, "x_m": pos.x, "y_m": pos.y,
            "source_lane_offset_m": _offset_m(pos, self.source_points)})
        self.rows["native_signal"].append({**common,
            "left_signal": left, "right_signal": right})
        self.rows["driver_check"].append({**common,
            "driver_check_observed": observed["observed"]})

    def write(self, output: str | Path, original_trace_id: str) -> dict:
        if not original_trace_id or any(len(rows) != 900 for rows in self.rows.values()):
            raise ValueError("complete 900-frame Native readbacks required")
        output = Path(output)
        output.mkdir(parents=True, exist_ok=True)
        entries = {}
        for name, rows in self.rows.items():
            packet = {"case_id": self.case_id, "source_kind": "original_native", "samples": rows}
            if name == "ego_pose":
                packet.update({"source_lane_id": self.packet["lanes"]["source"]["lane_id"],
                    "lane_geometry_source": self.packet["reviewed_provenance"]["lane_marking_source"]})
            if name == "native_signal":
                packet["readback_source"] = "CARLA actor.get_light_state Native API"
            if name == "driver_check":
                packet.update({"readback_source": self.check_source,
                    "observation_method": "independent original driver-input event readback; no cognition inference"})
            path = output / (name + ".json")
            if path.exists():
                raise ValueError("original Native readback already exists")
            path.write_text(json.dumps(packet, sort_keys=True, separators=(",", ":")) + "\n")
            entries[name] = {"path": path.name,
                             "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        inventory = {"case_id": self.case_id, "source_kind": "original_native",
                     "original_trace_id": original_trace_id, "sources": entries}
        (output / "readback-inventory.json").write_text(
            json.dumps(inventory, sort_keys=True, indent=2) + "\n")
        return inventory
