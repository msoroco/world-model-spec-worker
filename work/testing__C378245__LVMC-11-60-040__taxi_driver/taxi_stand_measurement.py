"""Saved-source measurements for a taxi stand and passenger exchange.

The procedure reports observed geometry and activity. Whether a stop is
expeditious or complies with other regulations remains a separate review.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT = "testing__C378245__LVMC-11-60-040__taxi_driver"
VIEWS = ("overview", "approach", "curb_reference", "passenger_side")


def raw_source(root: Path, ref: dict) -> bytes:
    if not isinstance(ref, dict) or not isinstance(ref.get("path"), str):
        raise ValueError("source path and digest required")
    path = Path(ref["path"])
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("source must stay beneath source root")
    raw = (root / path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref.get("sha256"):
        raise ValueError("source SHA256 differs")
    return raw


def record(root: Path, ref: dict) -> dict:
    return json.loads(raw_source(root, ref))


def finite(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("finite original " + name + " required")
    return float(value)


def polygon(value, name: str) -> list[tuple[float, float]]:
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError("reviewed " + name + " polygon required")
    points = []
    for point in value:
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError("reviewed " + name + " vertex required")
        points.append((finite(point[0], name + " x"), finite(point[1], name + " y")))
    return points


def within(point: tuple[float, float], shape: list[tuple[float, float]]) -> bool:
    x, y = point
    inside = False
    for i, (ax, ay) in enumerate(shape):
        bx, by = shape[(i + 1) % len(shape)]
        if (ay > y) != (by > y):
            crossing = ax + (y - ay) * (bx - ax) / (by - ay)
            if x < crossing:
                inside = not inside
    return inside


def measure(packet: dict, root: Path) -> dict:
    if (packet.get("assignment_id"), packet.get("cell_id"), packet.get("actor")) != (ASSIGNMENT, "C378245", "taxi_driver"):
        raise ValueError("taxi assignment identity differs")
    if packet.get("law_id") != "LVMC-11-60-040":
        raise ValueError("taxi law identity differs")
    case = packet.get("case_id")
    if not isinstance(case, str) or not case.startswith(ASSIGNMENT + "__"):
        raise ValueError("exact case identity required")
    site = record(root, packet.get("reviewed_site"))
    native = record(root, packet.get("native_result"))
    frames = record(root, packet.get("native_frames"))
    activity = record(root, packet.get("activity_review"))
    documents = {name: record(root, packet.get(name)) for name in
                 ("stand_designation", "taxi_licence", "other_regulations")}
    cameras = packet.get("camera_sources")
    if not isinstance(cameras, dict) or set(cameras) != set(VIEWS):
        raise ValueError("four original camera source references required")
    camera_hashes = {name: hashlib.sha256(raw_source(root, cameras[name])).hexdigest()
                     for name in VIEWS}
    if site.get("source_kind") != "original_independent_site_review":
        raise ValueError("original independent stand site review required")
    if site.get("cell_id") != "C378245" or site.get("business_district") is not True:
        raise ValueError("reviewed business-district cell differs")
    if site.get("street_public_access") is not True or not site.get("jurisdiction_review_id"):
        raise ValueError("street and jurisdiction review required")
    if site.get("map_sha256") != native.get("map_sha256"):
        raise ValueError("reviewed site differs from Native map")
    stand = polygon(site.get("stand_polygon_xy_m"), "stand")
    street = polygon(site.get("street_polygon_xy_m"), "street")
    if documents["stand_designation"].get("designation_id") != site.get("designation_id"):
        raise ValueError("taxi-stand designation differs")
    if documents["stand_designation"].get("authority_reviewed") is not True:
        raise ValueError("official stand designation review required")
    if documents["taxi_licence"].get("vehicle_id") != native.get("taxi_vehicle_id"):
        raise ValueError("licensed taxicab identity differs")
    if documents["taxi_licence"].get("operator_id") != native.get("operator_id"):
        raise ValueError("operator identity differs")
    if documents["other_regulations"].get("review_id") != site.get("other_regulation_review_id"):
        raise ValueError("other stop/parking regulation review differs")
    if native.get("source_kind") != "original_native" or native.get("case_id") != case:
        raise ValueError("original exact-case Native result required")
    if native.get("frame_count") != 900 or not isinstance(frames, list) or len(frames) != 900:
        raise ValueError("complete 900-frame Native history required")
    if native.get("recording_id") != packet.get("recording_id"):
        raise ValueError("original recording identity differs")
    if activity.get("source_kind") != "original_independent_activity_review":
        raise ValueError("independent passenger activity review required")
    if activity.get("recording_id") != packet["recording_id"] or activity.get("case_id") != case:
        raise ValueError("activity review identity differs")
    if activity.get("camera_sha256") != camera_hashes:
        raise ValueError("passenger review camera bytes differ")
    interval = activity.get("halt_interval_frames")
    if not isinstance(interval, list) or len(interval) != 2 or any(type(x) is not int for x in interval):
        raise ValueError("reviewed halt interval required")
    first, last = interval
    if not 0 <= first < last < 900:
        raise ValueError("reviewed halt interval outside capture")
    if activity.get("activity") not in ("park", "stand", "temporary_stop"):
        raise ValueError("reviewed activity type required")
    if not activity.get("reviewer_id"):
        raise ValueError("independent activity reviewer required")
    positions = []
    footprints = []
    speeds = []
    for i, row in enumerate(frames):
        if row.get("frame") != i or finite(row.get("elapsed_s"), "time") != i / 20:
            raise ValueError("original Native frame/time gap")
        xy = row.get("taxi_center_xy_m")
        if not isinstance(xy, list) or len(xy) != 2:
            raise ValueError("original taxi center missing")
        positions.append((finite(xy[0], "taxi x"), finite(xy[1], "taxi y")))
        body = row.get("taxi_footprint_xy_m")
        if not isinstance(body, list) or len(body) != 4:
            raise ValueError("four original taxi footprint corners required")
        corners = []
        for corner in body:
            if not isinstance(corner, list) or len(corner) != 2:
                raise ValueError("original taxi footprint corner missing")
            corners.append((finite(corner[0], "taxi body x"),
                            finite(corner[1], "taxi body y")))
        footprints.append(corners)
        speeds.append(finite(row.get("taxi_speed_mps"), "taxi speed"))
    halt_positions = positions[first:last + 1]
    halt_footprints = footprints[first:last + 1]
    halt_speeds = speeds[first:last + 1]
    if not all(within(xy, street) for corners in halt_footprints for xy in corners):
        raise ValueError("taxi halt lies outside reviewed street polygon")
    # 0.1 m/s is only an engineering stationarity tolerance, not legal duration.
    if max(halt_speeds) > 0.1:
        raise ValueError("reviewed halt interval includes moving taxi")
    events = activity.get("passenger_events")
    if not isinstance(events, list):
        raise ValueError("original passenger event review required")
    for event in events:
        if (event.get("kind") not in ("boarding", "alighting") or
            type(event.get("frame")) is not int or not first <= event["frame"] <= last or
            not event.get("passenger_actor_id") or event.get("observed") is not True):
            raise ValueError("passenger event lacks original review")
    return {
        "format": "worker-taxi-stand-measurement",
        "case_id": case,
        "recording_id": packet["recording_id"],
        "reviewed_activity": activity["activity"],
        "halt_interval_frames": interval,
        "max_halt_speed_mps": max(halt_speeds),
        "all_halt_centers_inside_designated_stand": all(within(xy, stand) for xy in halt_positions),
        "all_halt_centers_outside_designated_stand": all(not within(xy, stand) for xy in halt_positions),
        "all_halt_footprints_inside_designated_stand": all(
            within(xy, stand) for corners in halt_footprints for xy in corners),
        "all_halt_footprints_outside_designated_stand": all(
            not within(xy, stand) for corners in halt_footprints for xy in corners),
        "passenger_event_kinds": [event["kind"] for event in events],
        "source_sha256": {name: packet[name]["sha256"] for name in
                          ("reviewed_site", "native_result", "native_frames", "activity_review",
                           "stand_designation", "taxi_licence", "other_regulations")},
        "camera_sha256": camera_hashes,
        "expeditiousness": "requires_independent_review",
        "other_regulation_compliance": "requires_independent_review",
        "legal_verdict": None,
    }
