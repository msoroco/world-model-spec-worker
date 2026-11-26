"""Source-bound designated-place footprint and vehicle halt observations."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C229439__NRS-484B-500__vehicle_parker"


def _point(value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("two-dimensional point required")
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in value):
        raise ValueError("finite point required")
    return tuple(float(x) for x in value)


def _polygon(raw):
    if not isinstance(raw, list) or len(raw) < 3:
        raise ValueError("polygon required")
    points = [_point(p) for p in raw]
    area2 = sum(points[i][0] * points[(i + 1) % len(points)][1] - points[(i + 1) % len(points)][0] * points[i][1] for i in range(len(points)))
    if abs(area2) < 1e-8:
        raise ValueError("nondegenerate polygon required")
    return points


def _inside(p, polygon):
    x, y = p
    inside = False
    for i, a in enumerate(polygon):
        b = polygon[(i + 1) % len(polygon)]
        cross = (b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0])
        if abs(cross) < 1e-9 and min(a[0], b[0]) - 1e-9 <= x <= max(a[0], b[0]) + 1e-9 and min(a[1], b[1]) - 1e-9 <= y <= max(a[1], b[1]) + 1e-9:
            return True
        if (a[1] > y) != (b[1] > y):
            if x < a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]):
                inside = not inside
    return inside


def _segments_touch(a, b, c, d):
    def orientation(p, q, r):
        value = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        return 0 if abs(value) < 1e-9 else (1 if value > 0 else -1)

    def on_segment(p, q, r):
        return (min(p[0], r[0]) - 1e-9 <= q[0] <= max(p[0], r[0]) + 1e-9
                and min(p[1], r[1]) - 1e-9 <= q[1] <= max(p[1], r[1]) + 1e-9)

    turns = [orientation(a, b, c), orientation(a, b, d),
             orientation(c, d, a), orientation(c, d, b)]
    if turns[0] != turns[1] and turns[2] != turns[3]:
        return True
    return any(turn == 0 and on_segment(p, q, r) for turn, p, q, r in (
        (turns[0], a, c, b), (turns[1], a, d, b),
        (turns[2], c, a, d), (turns[3], c, b, d)))


def _overlaps(body, zone):
    if any(_inside(c, zone) for c in body) or any(_inside(c, body) for c in zone):
        return True
    return any(_segments_touch(body[i], body[(i + 1) % len(body)],
                               zone[j], zone[(j + 1) % len(zone)])
               for i in range(len(body)) for j in range(len(zone)))


def _footprint(center, heading_deg, length, width):
    center = _point(center)
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (heading_deg, length, width)):
        raise ValueError("finite vehicle dimensions and heading required")
    if length <= 0 or width <= 0:
        raise ValueError("positive vehicle dimensions required")
    theta = math.radians(heading_deg)
    forward = (math.cos(theta), math.sin(theta))
    left = (-forward[1], forward[0])
    return [(center[0] + sx * length / 2 * forward[0] + sy * width / 2 * left[0],
             center[1] + sx * length / 2 * forward[1] + sy * width / 2 * left[1])
            for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def _context(packet):
    if packet.get("assignment_id") != ASSIGNMENT or not packet.get("device_id") or not packet.get("designated_place_id"):
        raise ValueError("assignment, device and designated-place identity required")
    if not packet.get("device_instructions_source") or not packet.get("official_authority_source") or packet.get("device_erected") is not True:
        raise ValueError("erected official device and instruction/authority sources required")
    if not packet.get("hazard_or_congestion_source") or packet.get("hazard_or_congestion_status") not in ("hazardous", "congested", "unresolved"):
        raise ValueError("separate hazardous/congested place source required")
    return _polygon(packet.get("designated_place_polygon"))


def construct(site_path: str | Path, candidate_id: str) -> dict:
    path = Path(site_path)
    raw = path.read_bytes()
    site = json.loads(raw)
    zone = _context(site)
    if not site.get("map_id"):
        raise ValueError("source map identity required")
    candidates = site.get("parking_candidates")
    if not isinstance(candidates, dict) or candidate_id not in candidates:
        raise ValueError("named parking candidate required")
    candidate = candidates[candidate_id]
    corners = _footprint(candidate.get("center"), candidate.get("heading_deg"), candidate.get("length_m"), candidate.get("width_m"))
    inside = all(_inside(c, zone) for c in corners)
    requested_inside = candidate.get("requested_wholly_within_place")
    if not isinstance(requested_inside, bool):
        raise ValueError("requested designated-place occupation must be boolean")
    if requested_inside is not inside or (not requested_inside and _overlaps(corners, zone)):
        raise ValueError("candidate footprint does not match requested designated-place occupation")
    return {"assignment_id": ASSIGNMENT, "source": {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()},
            "candidate_id": candidate_id, "map_id": site["map_id"],
            "device_id": site["device_id"], "designated_place_id": site["designated_place_id"],
            "footprint_corners": [list(c) for c in corners], "wholly_within_designated_place": inside,
            "wholly_outside_designated_place": not _overlaps(corners, zone),
            "limit": "Static footprint intent only; original halt history and official designation require independent source review."}


def measure(trace_path: str | Path) -> dict:
    path = Path(trace_path)
    raw = path.read_bytes()
    packet = json.loads(raw)
    zone = _context(packet)
    if not packet.get("original_trace_id") or not packet.get("vehicle_actor_id") or not packet.get("parker_actor_id"):
        raise ValueError("original vehicle, parker and trace identities required")
    if not packet.get("loading_activity_source") or not packet.get("officer_or_device_direction_source"):
        raise ValueError("loading and officer/device direction sources required")
    frames = packet.get("frames")
    if not isinstance(frames, list) or len(frames) < 3:
        raise ValueError("three original frames required")
    observations = []
    previous = None
    for i, frame in enumerate(frames):
        t, speed = frame.get("time_s"), frame.get("speed_mps")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (t, speed)) or speed < 0:
            raise ValueError("finite nonnegative original time and speed required")
        if previous is not None and not 0 < t - previous <= 0.075:
            raise ValueError("ordered 20 Hz frames required")
        previous = t
        body = _polygon(frame.get("vehicle_footprint"))
        observations.append({"frame_index": i, "time_s": t, "speed_mps": speed,
                             "body_wholly_within_place": all(_inside(c, zone) for c in body),
                             "body_any_vertex_within_place": any(_inside(c, zone) for c in body),
                             "body_overlaps_place": _overlaps(body, zone),
                             "body_wholly_outside_place": not _overlaps(body, zone)})
    episodes = []
    start = None
    for i, observation in enumerate(observations):
        stationary_inside = (observation["speed_mps"] <= 0.1
                             and observation["body_wholly_within_place"])
        if stationary_inside and start is None:
            start = i
        if start is not None and (not stationary_inside or i == len(observations) - 1):
            end = i - 1 if not stationary_inside else i
            episodes.append({"first_frame": start, "last_frame": end,
                             "first_time_s": observations[start]["time_s"],
                             "last_time_s": observations[end]["time_s"],
                             "observed_span_s": observations[end]["time_s"] - observations[start]["time_s"]})
            start = None
    return {"assignment_id": ASSIGNMENT, "original_trace_id": packet["original_trace_id"],
            "source": {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()},
            "vehicle_actor_id": packet["vehicle_actor_id"], "parker_actor_id": packet["parker_actor_id"],
            "device_id": packet["device_id"], "designated_place_id": packet["designated_place_id"],
            "official_authority_source": packet["official_authority_source"],
            "hazard_or_congestion_status": packet["hazard_or_congestion_status"],
            "loading_activity_source": packet["loading_activity_source"],
            "officer_or_device_direction_source": packet["officer_or_device_direction_source"],
            "observations": observations,
            "stationary_wholly_inside_frames": [o["frame_index"] for o in observations if o["speed_mps"] <= 0.1 and o["body_wholly_within_place"]],
            "stationary_wholly_inside_episodes": episodes,
            "review_limit": "Engineering stationary threshold is not a legal stopping, standing or parking definition; device authority and place character remain independent review facts."}
