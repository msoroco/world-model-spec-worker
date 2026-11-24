"""Source-bound geometry and rest timeline for NRS 484B.500 diagnostics.

This measures an operator-supplied designated polygon; it never infers the
designation from sign position or decides the hazardous/congested legal issue.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
RATE_HZ = 20
REST_SPEED_MPS = 0.10  # Diagnostic tolerance, not a statutory threshold.


def _point(value):
    if not isinstance(value, list) or len(value) != 2 or any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
        for v in value
    ):
        raise ValueError("Invalid original geometry point")
    return tuple(float(v) for v in value)


def _polygon(value):
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError("Missing designated place or body polygon")
    polygon = [_point(p) for p in value]
    area = _area(polygon)
    if area <= 0.0:
        raise ValueError("Polygon must have positive counter-clockwise area")
    for i in range(len(polygon)):
        if not _inside(polygon[(i + 2) % len(polygon)], polygon[i], polygon[(i + 1) % len(polygon)]):
            raise ValueError("Polygon must be convex; split actual concave bounds into sourced parts")
    return polygon


def _area(poly):
    return sum(poly[i][0] * poly[(i + 1) % len(poly)][1]
               - poly[(i + 1) % len(poly)][0] * poly[i][1]
               for i in range(len(poly))) / 2.0


def _inside(p, a, b):
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= -1e-9


def _intersection(p, q, a, b):
    dx, dy = q[0] - p[0], q[1] - p[1]
    ex, ey = b[0] - a[0], b[1] - a[1]
    denominator = dx * ey - dy * ex
    if abs(denominator) < 1e-12:
        return q
    t = ((a[0] - p[0]) * ey - (a[1] - p[1]) * ex) / denominator
    return (p[0] + t * dx, p[1] + t * dy)


def _overlap(subject, clip):
    result = subject
    for i, a in enumerate(clip):
        b = clip[(i + 1) % len(clip)]
        preceding = result
        result = []
        if not preceding:
            break
        for j, q in enumerate(preceding):
            p = preceding[j - 1]
            pin, qin = _inside(p, a, b), _inside(q, a, b)
            if pin != qin:
                result.append(_intersection(p, q, a, b))
            if qin:
                result.append(q)
    return max(0.0, _area(result)) if len(result) >= 3 else 0.0


def _source(ref):
    if not isinstance(ref, dict) or not ref.get("path") or not ref.get("sha256"):
        raise ValueError("Missing original source reference")
    path = Path(ref["path"])
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]:
        raise ValueError("Missing or changed original source")
    return json.loads(path.read_text())


def measure(packet):
    """Measure complete time-aligned Native rows, returning no legal verdict."""
    if packet.get("format") != "worker-designated-stop-native-packet":
        raise ValueError("Unexpected Native source packet")
    sources = packet.get("sources", {})
    originals = {}
    for key in ("designation", "device", "map", "native_trace", "video_frame_map"):
        originals[key] = _source(sources.get(key))
    device = packet.get("device", {})
    if originals["device"] != {key: value for key, value in device.items() if key != "designated_polygon_map_m"}:
        raise ValueError("Device packet differs from original device source")
    if originals["designation"] != {"designated_polygon_map_m": device.get("designated_polygon_map_m")}:
        raise ValueError("Designation packet differs from original extent source")
    if device.get("authority_status") != "source_reviewed_official" or not device.get("erected"):
        raise ValueError("Official erected device source review missing")
    if not device.get("content") or not device.get("device_id"):
        raise ValueError("Device content or identity missing")
    if device.get("hazard_context_status") != "physical_facts_retained_legal_unresolved":
        raise ValueError("Hazard or congestion physical context missing")
    if device.get("active_first_frame") != 0 or device.get("active_last_frame") != FRAMES - 1:
        raise ValueError("Device erection interval does not cover capture")
    place = _polygon(device.get("designated_polygon_map_m"))
    rows = packet.get("rows")
    if originals["native_trace"] != rows:
        raise ValueError("Native rows differ from original trace source")
    if not isinstance(rows, list) or len(rows) != FRAMES:
        raise ValueError("Incomplete 30-second Native trace")
    if originals["video_frame_map"] != [{"video_frame": row.get("video_frame"), "time_s": row.get("time_s")}
                                         for row in rows]:
        raise ValueError("Video joins differ from original frame-map source")
    rest_frames, overlap_frames, rest_overlap_frames = 0, 0, 0
    min_overlap, max_overlap = math.inf, 0.0
    previous_at_rest = False
    rest_runs = []
    run_start = None
    for index, row in enumerate(rows):
        if row.get("video_frame") != index or row.get("native_frame") != index:
            raise ValueError("Native/video frame join failed")
        if abs(row.get("time_s", -1) - index / RATE_HZ) > 1e-6:
            raise ValueError("Native/video time join failed")
        speed = row.get("observed_speed_mps")
        if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not math.isfinite(speed) or speed < 0:
            raise ValueError("Missing observed Native speed")
        body = _polygon(row.get("vehicle_footprint_map_m"))
        area = _area(body)
        overlap = _overlap(body, place)
        ratio = overlap / area
        min_overlap, max_overlap = min(min_overlap, ratio), max(max_overlap, ratio)
        at_rest = speed <= REST_SPEED_MPS
        if at_rest:
            rest_frames += 1
            if not previous_at_rest:
                run_start = index
        elif previous_at_rest:
            rest_runs.append([run_start, index - 1])
            run_start = None
        previous_at_rest = at_rest
        if overlap > 1e-6:
            overlap_frames += 1
            if at_rest:
                rest_overlap_frames += 1
    if previous_at_rest:
        rest_runs.append([run_start, FRAMES - 1])
    if rest_frames == 0:
        raise ValueError("No observed vehicle rest interval")
    if not packet.get("person_caused_stop_source"):
        raise ValueError("Person-to-vehicle halt source missing")
    if not packet.get("traffic_and_direction_source"):
        raise ValueError("Traffic, police and device direction context missing")
    return {
        "format": "worker-designated-stop-measurement",
        "frames": FRAMES,
        "rate_hz": RATE_HZ,
        "duration_s": FRAMES / RATE_HZ,
        "rest_frames": rest_frames,
        "rest_runs_inclusive": rest_runs,
        "body_overlap_frames": overlap_frames,
        "rest_and_body_overlap_frames": rest_overlap_frames,
        "minimum_body_overlap_ratio": round(min_overlap, 6),
        "maximum_body_overlap_ratio": round(max_overlap, 6),
        "body_overlap_at_any_rest_frame": rest_overlap_frames > 0,
        "source_hashes": {k: v["sha256"] for k, v in sources.items()},
        "legal_characterization": "unassessed",
        "physical_completion": "requires_original_Native_sources",
    }
