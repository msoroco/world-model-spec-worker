"""Lazy CARLA actor readback for one observed sidewalk-bypass world tick.

The supplied camera synchronizer must retain the four original image payloads;
this reader verifies only their frame identity. No CARLA import is needed here.
"""
from __future__ import annotations

import math

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _vertices(actor):
    if actor is None or not getattr(actor, "is_alive", False):
        raise ValueError("observed Native actor is missing")
    box = getattr(actor, "bounding_box", None)
    if box is None:
        raise ValueError("observed Native actor has no bounding box")
    vertices = box.get_world_vertices(actor.get_transform())
    points = [[float(v.x), float(v.y)] for v in vertices]
    if len(points) < 4 or not all(math.isfinite(c) for point in points for c in point):
        raise ValueError("observed Native body geometry is incomplete")
    return points


def _center(actor):
    point = actor.get_transform().location
    x, y = float(point.x), float(point.y)
    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError("observed Native actor has nonfinite location")
    return x, y


class CarlaFrameReader:
    """Read original actor state after each controller tick.

    `camera_sync(frame)` must return a mapping from the four camera names to
    observed sensor-frame IDs, after retaining their original pixel payloads.
    An absent vehicle roster leaves traffic distance unmeasured and fails closed.
    For a missing sidewalk section, `gap_vertices_world_m` comes from the
    previously hashed original site survey rather than an invented obstacle.
    """

    def __init__(self, walker, obstruction, barrier, traffic_actors,
                 camera_sync, *, obstruction_kind: str,
                 gap_vertices_world_m=None, survey_transform=None):
        if obstruction_kind not in ("impassable_section", "missing_section"):
            raise ValueError("unknown sidewalk obstruction kind")
        if obstruction_kind == "impassable_section" and obstruction is None:
            raise ValueError("constructed sidewalk obstacle actor required")
        if obstruction_kind == "missing_section" and (obstruction is not None or
                not isinstance(gap_vertices_world_m, list) or len(gap_vertices_world_m) < 4):
            raise ValueError("observed missing sidewalk survey polygon required")
        if not traffic_actors:
            raise ValueError("original traffic actor roster required")
        if not callable(camera_sync):
            raise ValueError("four-camera synchronizer required")
        if not isinstance(survey_transform, dict) or not all(
                type(survey_transform.get(k)) in (int, float) for k in ("x", "y", "yaw_degrees")):
            raise ValueError("source-bound local-to-world transform required")
        self.walker, self.obstruction, self.barrier = walker, obstruction, barrier
        self.traffic_actors = tuple(traffic_actors)
        self.camera_sync = camera_sync
        self.kind = obstruction_kind
        self.gap = gap_vertices_world_m
        self.transform = survey_transform
        self.index = 0

    def __call__(self, sample: dict) -> dict:
        frame, time_s = sample["frame"], sample["time_s"]
        frames = self.camera_sync(frame)
        if not isinstance(frames, dict) or set(frames) != set(CAMERAS) or any(
                type(frames[name]) is not int or frames[name] != frame for name in CAMERAS):
            raise ValueError("four original camera frames do not join world tick")
        body = _vertices(self.walker)
        observed_center = _center(self.walker)
        if math.dist(observed_center, sample["position_world_xy_m"]) > .05:
            raise ValueError("pedestrian body readback differs from walking sample")
        obstruction = (_vertices(self.obstruction) if self.obstruction is not None
                       else [list(map(float, point[:2])) for point in self.gap])
        if len(obstruction) < 4 or not all(math.isfinite(c) for point in obstruction for c in point):
            raise ValueError("invalid observed sidewalk gap geometry")
        dx, dy = self.transform["x"], self.transform["y"]
        angle = math.radians(self.transform["yaw_degrees"])
        end = max((point[0] - dx) * math.cos(angle) +
                  (point[1] - dy) * math.sin(angle) for point in obstruction)
        distances = []
        for actor in self.traffic_actors:
            if not getattr(actor, "is_alive", False):
                raise ValueError("traffic roster actor disappeared during capture")
            distances.append(math.dist(observed_center, _center(actor)))
        common = {"frame": frame, "time_s": time_s}
        self.index += 1
        return {
            "video_frames.jsonl": {"carla_frame": frame, "video_frame": self.index - 1,
                                   "time_s": time_s},
            "pedestrian_history.jsonl": dict(common, body_vertices_world_m=body),
            "obstruction_history.jsonl": dict(common,
                intervening_barrier_present=self.barrier is not None,
                sidewalk_obstruction_end_local_m=end,
                sidewalk_obstruction_kind=self.kind,
                sidewalk_obstruction_vertices_world_m=obstruction,
                intervening_barrier_vertices_world_m=(
                    _vertices(self.barrier) if self.barrier is not None else None)),
            "traffic_history.jsonl": dict(common,
                nearest_traffic_distance_m=min(distances)),
        }
