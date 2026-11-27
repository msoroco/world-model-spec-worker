"""Saved original-source joins for the scooter pass; no legal safety verdict."""

import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from scene import FRAMES, HZ, FOOT_M

CAMERAS = {"overview", "approach", "reference_corner", "driver_reference"}
SOURCES = ("participant-poses.jsonl", "trace.jsonl", "video_frames.jsonl",
           "road.xodr", "pass-context.json", "capture/evidence.jsonl")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def _body(actor):
    corners = actor.get("body_xy_m")
    if not isinstance(corners, list) or len(corners) != 4:
        raise ValueError("Original four-corner body geometry missing")
    if any(len(p) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in p) for p in corners):
        raise ValueError("Original body coordinate invalid")
    x0 = sum(p[0] for p in corners) / 4
    y0 = sum(p[1] for p in corners) / 4
    ordered = sorted(corners, key=lambda p: math.atan2(p[1] - y0, p[0] - x0))
    if len({tuple(p) for p in ordered}) != 4:
        raise ValueError("Degenerate original body geometry")
    return ordered


def _segment_distance(a, b, c, d):
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    def on_segment(p, q, r):
        return min(p[0], r[0]) <= q[0] <= max(p[0], r[0]) and min(p[1], r[1]) <= q[1] <= max(p[1], r[1])
    if (o1 * o2 < 0 and o3 * o4 < 0) or any((o == 0 and on_segment(p, q, r)) for o, p, q, r in (
            (o1, a, c, b), (o2, a, d, b), (o3, c, a, d), (o4, c, b, d))):
        return 0.0
    def point_segment(p, q, r):
        dx, dy = r[0] - q[0], r[1] - q[1]
        t = max(0.0, min(1.0, ((p[0] - q[0]) * dx + (p[1] - q[1]) * dy) / (dx * dx + dy * dy)))
        return math.hypot(p[0] - q[0] - t * dx, p[1] - q[1] - t * dy)
    return min(point_segment(a, c, d), point_segment(b, c, d),
               point_segment(c, a, b), point_segment(d, a, b))


def surface_gap(a, b):
    left, right = _body(a), _body(b)
    def inside(point, polygon):
        crossing = False
        for i in range(4):
            p, q = polygon[i], polygon[(i + 1) % 4]
            if (p[1] > point[1]) != (q[1] > point[1]):
                x_at_y = p[0] + (point[1] - p[1]) * (q[0] - p[0]) / (q[1] - p[1])
                crossing ^= point[0] < x_at_y
        return crossing
    if inside(left[0], right) or inside(right[0], left):
        return 0.0
    return min(_segment_distance(left[i], left[(i + 1) % 4],
                                 right[j], right[(j + 1) % 4])
               for i in range(4) for j in range(4))


def measure(attempt):
    attempt = Path(attempt)
    for name in SOURCES:
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    context = json.loads((attempt / "pass-context.json").read_text())
    if context.get("statutory_subject") != "electric_scooter" or not context.get("scooter_actor_id"):
        raise ValueError("Original scooter identity context missing")
    if context.get("source_kind") not in ("native_original", "generated_software_diagnostic"):
        raise ValueError("Capture source kind missing")
    survey_path = context.get("survey_path")
    survey_path = Path(survey_path) if survey_path else None
    if survey_path is not None and not survey_path.is_absolute():
        survey_path = attempt / survey_path
    if survey_path is None or not survey_path.is_file() or sha(survey_path) != context.get("survey_sha256"):
        raise ValueError("Original scooter survey source missing or changed")
    from runner import survey_check
    survey = survey_check(json.loads(Path(survey_path).read_text()))
    if survey["device_blueprint"] != context.get("scooter_blueprint_id"):
        raise ValueError("Native scooter blueprint differs from surveyed identity")
    if context.get("same_direction_lane_count_authored") != 1:
        raise ValueError("One-lane activation context missing")
    road = ET.fromstring((attempt / "road.xodr").read_text())
    left = road.findall("road/lanes/laneSection/left/lane")
    right = road.findall("road/lanes/laneSection/right/lane")
    if [int(x.attrib["id"]) for x in left + right] != [1, -1]:
        raise ValueError("Original opposing lane readback differs")
    marking = right[0].find("roadMark").attrib.get("type")
    if marking != context.get("center_marking_authored"):
        raise ValueError("Original center marking differs from context")
    poses, traces, frames, captures = [rows(attempt / name) for name in
                                      ("participant-poses.jsonl", "trace.jsonl",
                                       "video_frames.jsonl", "capture/evidence.jsonl")]
    if any(len(table) != FRAMES for table in (poses, traces, frames, captures)):
        raise ValueError("Full original 600-frame source join required")
    overlap = []
    return_start = None
    prior_y = None
    for index, (pose, trace, frame_map, capture) in enumerate(zip(poses, traces, frames, captures)):
        native = pose.get("frame")
        if (pose.get("video_frame") != index or trace.get("frame") != native or
                frame_map.get("carla_frame") != native or capture.get("original_frame") != native):
            raise ValueError("Original frame identity differs")
        if set(frame_map.get("camera_native_frames", {})) != CAMERAS or any(
                value != native for value in frame_map["camera_native_frames"].values()):
            raise ValueError("Original four-camera frame join differs")
        time_s = pose.get("time_s")
        if type(time_s) not in (int, float) or not math.isfinite(time_s) or abs(time_s - frame_map.get("time_s", -999)) > .001:
            raise ValueError("Original time join differs")
        ego, scooter = pose.get("ego"), pose.get("scooter")
        if not isinstance(ego, dict) or not isinstance(scooter, dict):
            raise ValueError("Original participant pose missing")
        if ego.get("actor_id") == scooter.get("actor_id") or scooter.get("actor_id") != context["scooter_actor_id"]:
            raise ValueError("Original scooter actor identity changed")
        if scooter.get("blueprint_id") != context.get("scooter_blueprint_id"):
            raise ValueError("Original scooter blueprint identity changed")
        ebody, sbody = _body(ego), _body(scooter)
        ey = ego["center_xy_m"][1]
        if prior_y is not None and return_start is None and ey < prior_y - 1e-4:
            return_start = index
        prior_y = ey
        if max(p[0] for p in ebody) >= min(p[0] for p in sbody) and max(p[0] for p in sbody) >= min(p[0] for p in ebody):
            if ey <= scooter["center_xy_m"][1]:
                raise ValueError("Original pass was not left of scooter")
            overlap.append((index, surface_gap(ego, scooter)))
    if not overlap or return_start is None:
        raise ValueError("Original pass or right-return phase absent")
    min_frame, min_gap = min(overlap, key=lambda item: item[1])
    return {"format": "c272412-original-pass-measurement-v1",
            "source_kind": context["source_kind"],
            "original_native_observed": context["source_kind"] == "native_original",
            "minimum_body_surface_gap_m": min_gap, "minimum_gap_frame": min_frame,
            "three_foot_floor_m": 3 * FOOT_M, "three_foot_sampled_floor_met": min_gap >= 3 * FOOT_M,
            "abreast_frame_count": len(overlap), "first_abreast_frame": overlap[0][0],
            "last_abreast_frame": overlap[-1][0], "right_return_start_frame": return_start,
            "return_after_last_abreast_sample": return_start > overlap[-1][0],
            "original_frame_rate_hz": HZ, "sample_interval_s": 1 / HZ,
            "unobserved_between_frame_gap_possible": True,
            "safely_clear_legally_judged": False, "due_care_legally_judged": False,
            "center_crossing_safety_judged": False, "no_passing_rule_213_217_reviewed": False,
            "source_sha256": {name: sha(attempt / name) for name in SOURCES}}
