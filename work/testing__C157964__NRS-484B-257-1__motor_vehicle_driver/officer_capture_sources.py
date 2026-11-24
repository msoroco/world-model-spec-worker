"""Capture-time officer and ego sources without prelabeling camera observations.

The caller owns four original camera encoders and the Native actors. This writer
records synchronized identities and programmed pose readback. A later human or
independent pixel review writes officer_review.json bound to these files and
the four encoded camera bytes. It never infers observed direction from a pose.
"""

import json
import math
from pathlib import Path

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
PREFIX = "testing__C157964__NRS-484B-257-1__motor_vehicle_driver__"
ACTIVE = {PREFIX + "officer_active_stop_then_go", PREFIX + "officer_active_hold"}
INACTIVE = PREFIX + "officer_present_inactive"
ABSENT = PREFIX + "no_officer_yield_nearest_view"


def _finite(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Missing finite Native " + name)
    return float(value)


class OfficerSourceWriter:
    def __init__(self, root, context, frame_map_factory=None):
        self.root = Path(root)
        self.context = dict(context)
        self.frame_map_factory = frame_map_factory
        self.frame_map = None
        self.history = None
        self.count = 0
        case_id = self.context.get("case_id")
        if case_id not in ACTIVE | {INACTIVE, ABSENT}:
            raise ValueError("Unknown exact officer case")
        if case_id == ABSENT:
            if self.context.get("officer_actor_id") is not None:
                raise ValueError("No-officer capture has an officer identity")
        elif type(self.context.get("officer_actor_id")) is not int:
            raise ValueError("Native officer actor identity missing")

    def __enter__(self):
        if self.frame_map_factory is None:
            from worker_exchange.native_output import FrameMap
            self.frame_map_factory = FrameMap
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / "officer_context.json").open("x") as stream:
            stream.write(json.dumps(self.context, sort_keys=True, allow_nan=False) + "\n")
        self.frame_map = self.frame_map_factory(self.root / "video_frames.jsonl")
        self.history = (self.root / "officer_history.jsonl").open("x", buffering=1)
        return self

    def add_tick(self, snapshot, cameras, ego, officer, programmed_pose, through=None):
        if self.frame_map is None or self.history is None:
            raise ValueError("Officer source writer is not open")
        frame = snapshot.frame
        time_s = _finite(snapshot.timestamp.elapsed_seconds, "time")
        if type(frame) is not int or set(cameras) != set(CAMERAS):
            raise ValueError("Four original camera packets and frame required")
        for name in CAMERAS:
            packet = cameras[name]
            if packet.frame != frame or abs(_finite(packet.timestamp, name + " time") - time_s) > 1e-3:
                raise ValueError("Stale original officer camera packet: " + name)
        expected_id = self.context.get("officer_actor_id")
        if (getattr(officer, "id", None) if officer is not None else None) != expected_id:
            raise ValueError("Original officer actor differs from source context")
        if (programmed_pose.get("frame_index") != self.count or
                programmed_pose.get("officer_actor_id") != expected_id):
            raise ValueError("Programmed officer pose and original frame differ")
        command = programmed_pose.get("programmed_direction")
        applied = programmed_pose.get("pose_applied")
        active = self.context["case_id"] in ACTIVE
        if (type(applied) is not bool or
                (active and (command not in ("stop", "go") or not applied or
                             not programmed_pose.get("realized_bones"))) or
                (not active and (command != "none" or applied))):
            raise ValueError("Native officer pose differs from exact case program")
        vertices = ego.bounding_box.get_world_vertices(ego.get_transform())
        if len(vertices) < 8:
            raise ValueError("Complete original ego body vertices required")
        body = [[_finite(vertex.x, "ego body x"), _finite(vertex.y, "ego body y")]
                for vertex in vertices]
        velocity = ego.get_velocity()
        speed = math.sqrt(sum(_finite(getattr(velocity, axis), "ego velocity") ** 2
                              for axis in ("x", "y", "z")))
        row = {"frame": frame, "time_s": time_s, "officer_actor_id": expected_id,
               "programmed_direction": command,
               "native_pose_applied": applied,
               "ego": {"speed_mps": speed, "body_vertices_xy_m": body}}
        through_id = self.context.get("through_actor_id")
        if through_id is not None:
            if through is None or getattr(through, "id", None) != through_id:
                raise ValueError("Original through actor differs from source context")
            through_vertices = through.bounding_box.get_world_vertices(through.get_transform())
            if len(through_vertices) < 8:
                raise ValueError("Complete original through body vertices required")
            through_velocity = through.get_velocity()
            row["through"] = {
                "actor_id": through_id,
                "speed_mps": math.sqrt(sum(_finite(getattr(through_velocity, axis),
                                                  "through velocity") ** 2
                                           for axis in ("x", "y", "z"))),
                "body_vertices_xy_m": [[_finite(vertex.x, "through body x"),
                                        _finite(vertex.y, "through body y")]
                                       for vertex in through_vertices]}
        if programmed_pose.get("realized_bones"):
            row["realized_bones"] = programmed_pose["realized_bones"]
        self.frame_map.append(frame, time_s,
                              camera_frames={name: cameras[name].frame for name in CAMERAS})
        self.history.write(json.dumps(row, allow_nan=False) + "\n")
        self.count += 1
        return row

    def __exit__(self, *args):
        try:
            if self.history is not None:
                self.history.close()
        finally:
            if self.frame_map is not None:
                self.frame_map.close()
