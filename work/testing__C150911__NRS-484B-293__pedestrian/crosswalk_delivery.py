"""CPU construction and original-sample measurement for NRS 484B.293.

Right/left is defined relative to the pedestrian's direction of passage. The
returned geometry is an observation, never a legal practicability decision.
"""
from __future__ import annotations

import hashlib
import json
import math


def _point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("two-dimensional source point required")
    result = tuple(float(x) for x in value)
    if not all(math.isfinite(x) for x in result):
        raise ValueError("nonfinite source point")
    return result


def _vector(site):
    start, end = _point(site["entry_center"]), _point(site["exit_center"])
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if length < 2:
        raise ValueError("crosswalk passage too short")
    return start, length, (dx / length, dy / length), (dy / length, -dx / length)


def validate_site(site):
    """Reject ungrounded walkways and missing qualification/context sources."""
    for key in ("map_sha256", "crosswalk_source_sha256", "crosswalk_id",
                "one_way_road_id", "access_source_sha256", "signal_source_sha256",
                "obstacle_source_sha256", "participant_source_sha256",
                "pedestrian_source_sha256"):
        value = site.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError("missing site source: " + key)
    if site.get("crosswalk_qualification") != "native_crosswalk_readback":
        raise ValueError("native crosswalk qualification readback required")
    width = float(site["crosswalk_width_m"])
    if not math.isfinite(width) or width <= 1:
        raise ValueError("invalid crosswalk width")
    _vector(site)
    if site.get("governing_signal") not in ("none_read_back", "pedestrian_walk",
                                             "pedestrian_dont_walk"):
        raise ValueError("governing pedestrian signal unknown")
    if site.get("pedestrian_access") is not True:
        raise ValueError("pedestrian access unverified")
    return True


def waypoints(site, side, stations=(0.0, 0.25, 0.5, 0.75, 1.0)):
    validate_site(site)
    if side not in ("right", "left"):
        raise ValueError("unknown half target")
    start, length, forward, right = _vector(site)
    offset = float(site["crosswalk_width_m"]) * (0.25 if side == "right" else -0.25)
    if any(not 0 <= float(s) <= 1 for s in stations):
        raise ValueError("station outside passage")
    return [(start[0] + forward[0] * length * s + right[0] * offset,
             start[1] + forward[1] * length * s + right[1] * offset)
            for s in stations]


def spawn_walk(site, side, adapter):
    """Lazy Native bridge; adapter owns blueprint, spawn and cleanup."""
    points = waypoints(site, side)
    walker = adapter.spawn_pedestrian(points[0], site["crosswalk_id"])
    if walker is None:
        raise ValueError("pedestrian spawn failed")
    try:
        adapter.set_pedestrian_route(walker, points)
    except Exception:
        adapter.destroy(walker)
        raise
    return walker, points


def measure(site, samples, obstacle_samples, participant_samples):
    """Measure full original 20 Hz passage and retain the raw stream."""
    validate_site(site)
    if not samples or not obstacle_samples or not participant_samples:
        raise ValueError("missing original participant/obstacle samples")
    start, length, forward, right = _vector(site)
    width = float(site["crosswalk_width_m"])
    if any(type(row.get("frame")) is not int for row in samples):
        raise ValueError("original frame identity invalid")
    frames = [row["frame"] for row in samples]
    if frames != list(range(frames[0], frames[0] + len(frames))):
        raise ValueError("nonconsecutive original frames")
    if any(type(row.get("elapsed_s")) not in (int, float) or
           not math.isfinite(row["elapsed_s"]) for row in samples):
        raise ValueError("original elapsed time invalid")
    times = [float(row["elapsed_s"]) for row in samples]
    if any(abs((times[i] - times[i - 1]) - 0.05) > 0.001 for i in range(1, len(times))):
        raise ValueError("original samples must be 20 Hz")
    for name, stream in (("obstacle", obstacle_samples), ("participant", participant_samples)):
        if [int(row["frame"]) for row in stream] != frames:
            raise ValueError(name + " frame join missing")
    trace = []
    pedestrian_id = samples[0].get("pedestrian_id")
    if not pedestrian_id:
        raise ValueError("original pedestrian identity missing")
    for row, obstacle, participant in zip(samples, obstacle_samples, participant_samples):
        if (row.get("pedestrian_id") != pedestrian_id or
            row.get("pedestrian_source_sha256") != site["pedestrian_source_sha256"]):
            raise ValueError("original pedestrian identity/source changed")
        if obstacle.get("source_sha256") != site["obstacle_source_sha256"]:
            raise ValueError("obstacle source binding differs")
        if participant.get("source_sha256") != site["participant_source_sha256"]:
            raise ValueError("participant source binding differs")
        x, y = _point(row["pedestrian_xy"])
        rel = (x - start[0], y - start[1])
        station = rel[0] * forward[0] + rel[1] * forward[1]
        lateral = rel[0] * right[0] + rel[1] * right[1]
        available = float(obstacle["available_right_width_m"])
        if not math.isfinite(available) or available < 0 or available > width / 2:
            raise ValueError("invalid available right width")
        if not isinstance(participant.get("participants"), list):
            raise ValueError("missing participant inventory")
        trace.append({"frame": row["frame"], "elapsed_s": float(row["elapsed_s"]),
                      "pedestrian_id": pedestrian_id,
                      "pedestrian_source": site["pedestrian_source_sha256"],
                      "station_m": station, "right_lateral_m": lateral,
                      "within_crosswalk": 0 <= station <= length and abs(lateral) <= width / 2,
                      "obstacle_source": obstacle["source_sha256"],
                      "participant_source": participant["source_sha256"],
                      "available_right_width_m": available,
                      "nearby_participants": participant["participants"]})
    return {"site_source_sha256": hashlib.sha256(json.dumps(site, sort_keys=True).encode()).hexdigest(),
            "fixed_sources": {key: site[key] for key in ("map_sha256", "crosswalk_source_sha256",
                              "crosswalk_id", "one_way_road_id", "access_source_sha256",
                              "signal_source_sha256", "obstacle_source_sha256",
                              "participant_source_sha256", "pedestrian_source_sha256")},
            "full_original_trace": trace, "right_half_sample_count": sum(r["right_lateral_m"] > 0 for r in trace),
            "crosswalk_sample_count": sum(r["within_crosswalk"] for r in trace),
            "legal_practicability": "unresolved"}


def audit_pair(left, right, deliberate_fields):
    """Independent exact-source comparison over saved measurement summaries."""
    required = {"site_source_sha256", "fixed_sources", "full_original_trace", "legal_practicability"}
    if not required <= set(left) or not required <= set(right):
        raise ValueError("missing saved measurement source")
    if left["legal_practicability"] != "unresolved" or right["legal_practicability"] != "unresolved":
        raise ValueError("unsupported practicability verdict")
    for key, value in left["fixed_sources"].items():
        if key not in deliberate_fields and value != right["fixed_sources"].get(key):
            raise ValueError("fixed site differs: " + key)
    for item in (left, right):
        if not item["full_original_trace"]:
            raise ValueError("missing original trace")
        frames = [r["frame"] for r in item["full_original_trace"]]
        if frames != list(range(frames[0], frames[0] + len(frames))):
            raise ValueError("gapped original trace")
    return {"passed": True, "fixed_sources_checked": sorted(set(left["fixed_sources"]) - set(deliberate_fields)),
            "compared_original_frames": [len(left["full_original_trace"]), len(right["full_original_trace"])]}
