"""Source-shaped divided-roadway geometry measurement for NRS 484B.227(1).

Overlap is measured from original body footprints and surveyed convex map
polygons. A geometric opening is never treated as public authorization.
"""
from math import isfinite
import re

CAMERAS = ("front", "rear", "left", "right")


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError("missing or nonfinite " + name)
    return float(value)


def polygon(value, name):
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError("missing " + name + " polygon")
    points = []
    for point in value:
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError("malformed " + name + " polygon")
        points.append((number(point[0], name + " x"), number(point[1], name + " y")))
    area = sum(points[i][0] * points[(i + 1) % len(points)][1] - points[(i + 1) % len(points)][0] * points[i][1] for i in range(len(points)))
    if abs(area) < 1e-6:
        raise ValueError("degenerate " + name + " polygon")
    signs = set()
    for i in range(len(points)):
        a, b, c = points[i], points[(i + 1) % len(points)], points[(i + 2) % len(points)]
        cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if abs(cross) > 1e-8:
            signs.add(cross > 0)
    if len(signs) > 1:
        raise ValueError("nonconvex " + name + " polygon requires surveyed decomposition")
    return points


def overlaps(first, second):
    """Separating-axis test for two convex 2-D footprints."""
    for shape in (first, second):
        for i, a in enumerate(shape):
            b = shape[(i + 1) % len(shape)]
            axis = (a[1] - b[1], b[0] - a[0])
            left = [x * axis[0] + y * axis[1] for x, y in first]
            right = [x * axis[0] + y * axis[1] for x, y in second]
            if max(left) < min(right) or max(right) < min(left):
                return False
    return True


def measure(frames, map_context, *, source_kind, camera_names=CAMERAS):
    if source_kind not in ("original_native", "synthetic_native_sample"):
        raise ValueError("undeclared source kind")
    if len(frames) < 600:
        raise ValueError("capture shorter than 30 seconds at 20 Hz")
    if map_context.get("layout") != "divided_road":
        raise ValueError("divided-road survey missing")
    median = polygon(map_context.get("median_polygon"), "median")
    opening = polygon(map_context.get("opening_polygon"), "opening")
    right_roadway = polygon(map_context.get("right_roadway_polygon"), "right roadway")
    opposite_roadway = polygon(map_context.get("opposite_roadway_polygon"), "opposite roadway")
    authority = map_context.get("opening_authority_source")
    if not isinstance(authority, dict) or not authority.get("path") or not re.fullmatch(r"[0-9a-f]{64}", authority.get("sha256", "")):
        raise ValueError("public-authority source reference missing")
    first_time = previous_time = None
    median_frames = opening_frames = median_only_frames = right_frames = opposite_frames = 0
    for i, frame in enumerate(frames):
        if frame.get("frame_id") != i:
            raise ValueError("nonconsecutive original frame map")
        time = number(frame.get("sim_time_s"), "frame time")
        if first_time is None:
            first_time = time
        if previous_time is not None and abs(time - previous_time - 0.05) > 1e-5:
            raise ValueError("20 Hz frame timing gap")
        previous_time = time
        camera_frames = frame.get("camera_frames")
        if not isinstance(camera_frames, dict) or set(camera_frames) != set(camera_names) or any(camera_frames[name] != i for name in camera_names):
            raise ValueError("four source-camera frame join missing or mismatched")
        body = polygon(frame.get("ego_footprint"), "ego footprint")
        number(frame.get("ego_heading_deg"), "ego heading")
        in_median = overlaps(body, median)
        in_opening = overlaps(body, opening)
        median_frames += int(in_median)
        opening_frames += int(in_opening)
        median_only_frames += int(in_median and not in_opening)
        right_frames += int(overlaps(body, right_roadway))
        opposite_frames += int(overlaps(body, opposite_roadway))
    if previous_time - first_time + 0.05 < 30 - 1e-5:
        raise ValueError("capture shorter than 30 seconds")
    return {
        "format": "divided-road-geometry-measurement-v1", "source_kind": source_kind,
        "frame_count": len(frames), "median_overlap_frames": median_frames,
        "opening_overlap_frames": opening_frames,
        "median_without_opening_overlap_frames": median_only_frames,
        "right_roadway_overlap_frames": right_frames,
        "opposite_roadway_overlap_frames": opposite_frames,
        "authority_reference_present": True,
        "authority_verified": False, "legal_judgment": "unresolved",
    }
