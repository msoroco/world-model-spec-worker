"""Source-bound signed-entrance observations; no legal judgment is computed."""

import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Missing finite " + label)
    return float(value)


def analyze(attempt, config, history, frames, review):
    attempt = Path(attempt)
    site = config["site"]
    source = attempt / "officer-site.xodr"
    if not source.is_file() or _sha(source) != site["xodr_sha256"]:
        raise ValueError("Signed entrance OpenDRIVE source differs")
    site_review = review.get("site_review")
    if not isinstance(site_review, dict) or site_review.get("sign_id") != site["yield_sign_id"]:
        raise ValueError("Missing exact signed-entrance review")
    if site_review.get("sign_face_observed") not in ("yield", "stop", "unverified"):
        raise ValueError("Missing original sign-face review")
    if site_review.get("proper_sign_judgment") != "unresolved" or site_review.get("nearest_view_judgment") != "unresolved":
        raise ValueError("Signed entrance review must preserve unresolved judgments")
    if site_review.get("source_camera") not in (name + ".mkv" for name in CAMERAS):
        raise ValueError("Signed entrance review needs original camera source")
    officer_context = json.loads((attempt / "officer_context.json").read_text())
    polygon = Polygon(officer_context["intersection_polygon_xy_m"])
    if not polygon.is_valid or polygon.area <= 0 or len(history) != len(frames) or len(history) != len(review["frames"]):
        raise ValueError("Incomplete signed-entrance source history")
    channels = {name: [] for name in (
        "through_highway_sight_clear", "ego_distance_to_junction_m",
        "through_vehicle_position", "through_vehicle_speed",
        "ego_crossing_body", "ego_approach_speed")}
    for row, frame, observed in zip(history, frames, review["frames"]):
        fid, time = row.get("frame"), _finite(row.get("time_s"), "site time")
        if fid != frame.get("carla_frame") or fid != observed.get("frame") or time != frame.get("time_s"):
            raise ValueError("Signed-entrance camera/history join failed")
        sight = observed.get("through_highway_sight_clear")
        if type(sight) is not bool or observed.get("sight_frame_source") not in (name + ".mkv" for name in CAMERAS):
            raise ValueError("Missing original through-highway sight review")
        ego, through = row.get("ego"), row.get("through")
        if not isinstance(ego, dict) or not isinstance(through, dict):
            raise ValueError("Missing ego/through source bodies")
        if through.get("actor_id") != officer_context["through_actor_id"]:
            raise ValueError("Through actor differs from signed-entrance source")
        ego_points, through_points = ego.get("body_vertices_xy_m"), through.get("body_vertices_xy_m")
        if not isinstance(ego_points, list) or len(ego_points) < 4 or not isinstance(through_points, list) or len(through_points) < 4:
            raise ValueError("Incomplete original crossing bodies")
        ego_body = MultiPoint([(_finite(p[0], "ego x"), _finite(p[1], "ego y")) for p in ego_points]).convex_hull
        through_body = MultiPoint([(_finite(p[0], "through x"), _finite(p[1], "through y")) for p in through_points]).convex_hull
        values = {
            "through_highway_sight_clear": int(sight),
            "ego_distance_to_junction_m": ego_body.distance(polygon),
            "through_vehicle_position": {"body_vertices_xy_m": through_points, "center_xy_m": list(through_body.centroid.coords[0])},
            "through_vehicle_speed": {"speed_mps": _finite(through.get("speed_mps"), "through speed")},
            "ego_crossing_body": {"body_vertices_xy_m": ego_points, "inside_junction": ego_body.intersects(polygon)},
            "ego_approach_speed": _finite(ego.get("speed_mps"), "ego speed"),
        }
        for name, value in values.items():
            channels[name].append({"original_frame": fid, "time_s": time, "value": value})
    source_hashes = {name: _sha(attempt / name) for name in (
        "officer-site.xodr", "officer_history.jsonl", "officer_review.json", "video_frames.jsonl")}
    source_hashes.update({name + ".mkv": _sha(attempt / (name + ".mkv")) for name in CAMERAS})
    context = {"yield_site_review": {
        "sign_id": site["yield_sign_id"], "sign_face_observed": site_review["sign_face_observed"],
        "source_camera": site_review["source_camera"],
        "stop_line_observed": site_review.get("stop_line_observed"),
        "crosswalk_observed": site_review.get("crosswalk_observed"),
        "proper_sign_judgment": "unresolved", "nearest_view_judgment": "unresolved",
        "immediate_hazard_judgment": "unresolved", "right_of_way_judgment": "unresolved",
        "review_provenance_kind": review.get("provenance_kind"), "source_sha256": source_hashes}}
    return channels, context
