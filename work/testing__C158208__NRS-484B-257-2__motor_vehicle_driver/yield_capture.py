"""Capture exact Native body and camera joins for the signed entrance.

The caller supplies an independently reviewed reference boundary and site
context. This module records geometry and motion; it does not decide whether
the sign is proper, an approach is an immediate hazard, or a driver complies.
"""

import hashlib
import json
import math
from pathlib import Path

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Missing finite " + label)
    return float(value)


def _xy(point):
    return [_finite(point.x, "body x"), _finite(point.y, "body y")]


def _vertices(actor):
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    if len(vertices) < 4:
        raise ValueError("Native actor has no complete body")
    footprint = sorted(set(tuple(_xy(vertex)) for vertex in vertices))
    if len(footprint) < 4:
        raise ValueError("Native actor has degenerate body")
    return [list(point) for point in footprint]


def _boundary(review):
    boundary = review.get("reference_boundary")
    if not isinstance(boundary, dict) or boundary.get("source") not in (
            "marked_stop_line", "near_crosswalk", "nearest_view_point"):
        raise ValueError("Missing reviewed subsection-1 reference boundary")
    origin, forward = boundary.get("origin_xy_m"), boundary.get("ego_forward_xy")
    if not isinstance(origin, list) or not isinstance(forward, list) or len(origin) != 2 or len(forward) != 2:
        raise ValueError("Invalid reviewed reference boundary")
    origin = [_finite(v, "reference origin") for v in origin]
    forward = [_finite(v, "ego forward") for v in forward]
    length = math.hypot(*forward)
    if not math.isclose(length, 1.0, abs_tol=1e-6):
        raise ValueError("Reference forward vector must be unit length")
    selected = ("marked_stop_line" if review.get("marked_stop_line_observed") is True
                else "near_crosswalk" if review.get("near_crosswalk_observed") is True
                else "nearest_view_point")
    if boundary["source"] != selected:
        raise ValueError("Reference boundary differs from ordered source review")
    if selected == "nearest_view_point" and origin != review.get("nearest_view_point_xy_m"):
        raise ValueError("Nearest-view boundary differs from reviewed point")
    return origin, forward


class EntrySourceWriter:
    """Append one source row only after all four cameras return a Native tick."""

    def __init__(self, root, context, review, ego, other, sign):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.context = dict(context)
        self.origin, self.forward = _boundary(review)
        if (self.context.get("native_yield_sign_id") != sign.id
                or self.context.get("ego_entrance_device") != "yield"
                or self.context.get("non_through_highway") is not True):
            raise ValueError("Native yield identity or site status differs")
        if ego.id == other.id:
            raise ValueError("Ego and other actor must differ")
        self.ego, self.other, self.sign = ego, other, sign
        self.previous_frame = -1
        self.previous_time = -math.inf
        self.count = 0
        for name in ("intersection_context.json", "entry_history.jsonl", "video_frames.jsonl"):
            if (self.root / name).exists():
                raise ValueError("Source already exists: " + name)
        (self.root / "intersection_context.json").write_text(json.dumps(context, sort_keys=True, indent=2) + "\n")

    def add(self, world, frame, time_s, camera_frame_ids):
        """Record a synchronized tick; camera_frame_ids are sensor callback frames."""
        if type(frame) is not int or frame <= self.previous_frame or world.get_snapshot().frame != frame:
            raise ValueError("Missing current monotone Native frame")
        time_s = _finite(time_s, "Native time")
        if time_s <= self.previous_time:
            raise ValueError("Nonmonotone Native time")
        if not isinstance(camera_frame_ids, dict) or set(camera_frame_ids) != set(CAMERAS):
            raise ValueError("Four original cameras required")
        if any(type(value) is not int or value != frame for value in camera_frame_ids.values()):
            raise ValueError("Camera callback frame differs from Native tick")
        ego_body = _vertices(self.ego)
        other_body = _vertices(self.other)
        velocity = self.ego.get_velocity()
        speed = math.sqrt(sum(_finite(getattr(velocity, axis), "ego velocity") ** 2
                              for axis in ("x", "y", "z")))
        before = all(sum((point[i] - self.origin[i]) * self.forward[i] for i in (0, 1)) < 0
                     for point in ego_body)
        if world.get_snapshot().frame != frame:
            raise ValueError("World advanced during Native source observation")
        row = {"frame": frame, "time_s": time_s,
               "ego_actor_id": self.ego.id, "other_actor_id": self.other.id,
               "ego_road_id": self.context["ego_approach_road_id"],
               "yield_sign_id": self.sign.id, "ego_speed_mps": speed,
               "ego_body_before_yield_reference": before,
               "ego_body_vertices_xy_m": ego_body,
               "other_body_vertices_xy_m": other_body}
        join = {"video_frame": self.count, "carla_frame": frame, "time_s": time_s,
                "camera_frame_ids": camera_frame_ids}
        for name, value in (("entry_history.jsonl", row), ("video_frames.jsonl", join)):
            with (self.root / name).open("a") as handle:
                handle.write(json.dumps(value, sort_keys=True) + "\n")
        self.previous_frame, self.previous_time = frame, time_s
        self.count += 1


def bind_site_review(root, findings):
    """Bind human/source-camera findings to a completed four-camera capture."""
    root = Path(root)
    if (root / "site_review.json").exists():
        raise ValueError("Site review already exists")
    context = json.loads((root / "intersection_context.json").read_text())
    frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
    if not frames or any(set(row.get("camera_frame_ids", {})) != set(CAMERAS)
                         or any(value != row.get("carla_frame") for value in row["camera_frame_ids"].values())
                         for row in frames):
        raise ValueError("Incomplete original four-camera frame joins")
    hashes = {}
    for name in CAMERAS:
        path = root / (name + ".mkv")
        if not path.is_file() or not path.stat().st_size:
            raise ValueError("Missing original camera: " + name)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    review = dict(findings)
    if review.get("native_yield_sign_id") != context.get("native_yield_sign_id"):
        raise ValueError("Review sign identity differs")
    _boundary(review)
    review["intersection_context_sha256"] = hashlib.sha256((root / "intersection_context.json").read_bytes()).hexdigest()
    review["camera_sha256"] = hashes
    review["reviewed_carla_frames"] = [row["carla_frame"] for row in frames]
    review["reviewed_frame_count"] = len(frames)
    (root / "site_review.json").write_text(json.dumps(review, sort_keys=True, indent=2) + "\n")
    return review
