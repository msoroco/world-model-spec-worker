"""Source-bound measurements for the assigned one-way red-left branch.

The output is physical description, never a statutory verdict. A fixture can
test this code but cannot establish that a reviewed CARLA site exists.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def _number(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("missing finite " + name)
    return float(value)


def _xy(value, name):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("missing XY " + name)
    return (_number(value[0], name), _number(value[1], name))


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_site(packet_path):
    """Validate retained source custody and stated lane/stop geometry."""
    packet_path = Path(packet_path).resolve()
    packet = json.loads(packet_path.read_text())
    if packet.get("format") != "c153046-red-left-site-v1" or not packet.get("reviewer"):
        raise ValueError("unreviewed exact site packet")
    sources = packet.get("sources")
    if not isinstance(sources, dict) or set(sources) != {
        "opendrive", "official_signal", "one_way_routes", "stop_reference"
    }:
        raise ValueError("incomplete site source inventory")
    for name, source in sources.items():
        if not isinstance(source, dict) or not source.get("citation") or not source.get("reviewer"):
            raise ValueError("uncited site source: " + name)
        path = (packet_path.parent / source.get("path", "")).resolve()
        if not path.is_relative_to(packet_path.parent) or not path.is_file() or _sha(path) != source.get("sha256"):
            raise ValueError("source bytes missing or changed: " + name)
    if packet.get("approach_one_way") is not True or packet.get("receiving_one_way_to_left") is not True:
        raise ValueError("one-way directions unreviewed")
    direction = _xy(packet.get("approach_direction_xy"), "approach direction")
    outgoing = _xy(packet.get("receiving_direction_xy"), "receiving direction")
    if abs(math.hypot(*direction) - 1) > 0.01 or abs(math.hypot(*outgoing) - 1) > 0.01 or _cross(direction, outgoing) < 0.7:
        raise ValueError("receiving route does not turn left")
    reference = _xy(packet.get("approach_reference_xy"), "approach reference")
    lanes = packet.get("approach_lane_centers_xy")
    if not isinstance(lanes, dict) or len(lanes) < 2:
        raise ValueError("distinct approach lanes missing")
    lateral = {key: _cross(direction, tuple(point[i] - reference[i] for i in (0, 1)))
               for key, point in ((key, _xy(value, "lane")) for key, value in lanes.items())}
    extreme = max(lateral, key=lateral.get)
    if packet.get("extreme_left_lane_id") != extreme or len({round(x, 3) for x in lateral.values()}) != len(lateral):
        raise ValueError("extreme-left position unverified")
    signal = packet.get("signal", {})
    if signal.get("official") is not True or signal.get("head_configuration") != "steady_red_alone" or not signal.get("native_actor_id"):
        raise ValueError("official red-alone signal unverified")
    stop = packet.get("stop_reference", {})
    if stop.get("kind") not in {"marked_crosswalk", "signed_or_marked_stop", "intersection_entry"} or stop.get("hierarchy_reviewed") is not True:
        raise ValueError("applicable stop hierarchy unreviewed")
    stop_point = _xy(stop.get("point_xy"), "stop reference")
    return {"source_packet_sha256": _sha(packet_path), "direction": direction,
            "reference": reference, "stop_progress_m": _dot(tuple(stop_point[i] - reference[i] for i in (0, 1)), direction),
            "left_lane_id": extreme, "signal_actor_id": str(signal["native_actor_id"]),
            "stop_kind": stop["kind"]}


def measure(packet_path, trace_path, case_id):
    """Measure a sealed 20 Hz original history without substituting requests."""
    site = validate_site(packet_path)
    rows = [json.loads(line) for line in Path(trace_path).read_text().splitlines() if line.strip()]
    if len(rows) < 2:
        raise ValueError("original history too short")
    measurements = []
    previous = None
    for row in rows:
        if row.get("case_id") != case_id or row.get("source_packet_sha256") != site["source_packet_sha256"]:
            raise ValueError("case or source identity differs")
        frame = row.get("native_frame", {})
        if frame.get("origin") != "native_world_snapshot" or str(frame.get("signal_actor_id")) != site["signal_actor_id"]:
            raise ValueError("original signal source missing")
        index = frame.get("frame")
        time_s = _number(frame.get("time_s"), "frame time")
        if type(index) is not int or (previous and (index != previous[0] + 1 or abs(time_s - previous[1] - 0.05) > 0.001)):
            raise ValueError("original 20 Hz sequence broken")
        previous = index, time_s
        ego = frame.get("ego", {})
        if ego.get("lane_id") not in {site["left_lane_id"], "receiving"}:
            raise ValueError("ego left-turn lane source missing")
        vertices = ego.get("body_vertices_xy")
        if not isinstance(vertices, list) or len(vertices) < 4:
            raise ValueError("full original ego body missing")
        front = max(_dot(tuple(p[i] - site["reference"][i] for i in (0, 1)), site["direction"])
                    for p in (_xy(value, "ego vertex") for value in vertices))
        speed = _number(ego.get("speed_m_s"), "actual ego speed")
        actors = frame.get("directed_participants")
        if not isinstance(actors, list):
            raise ValueError("signal-directed participant inventory missing")
        for actor in actors:
            if not actor.get("native_actor_id") or not isinstance(actor.get("conflict_zone_occupied"), bool) or not actor.get("source_citation"):
                raise ValueError("participant source or conflict missing")
        measurements.append({"frame": index, "time_s": time_s,
                             "red_alone": frame.get("signal_state") == "steady_red_alone",
                             "front_progress_m": front, "actual_speed_m_s": speed,
                             "crossed_stop_reference": front > site["stop_progress_m"],
                             "directed_conflict": any(x["conflict_zone_occupied"] for x in actors)})
    first_entry = next((i for i, x in enumerate(measurements) if x["crossed_stop_reference"]), None)
    prior = measurements if first_entry is None else measurements[:first_entry]
    stops = [x for x in prior if x["actual_speed_m_s"] <= 0.05 and x["red_alone"]]
    conflict_entry = [] if first_entry is None else [x for x in measurements[first_entry:] if x["red_alone"] and x["directed_conflict"]]
    return {"case_id": case_id, "site_sha256": site["source_packet_sha256"],
            "trace_sha256": _sha(trace_path), "original_frames": len(measurements),
            "stop_reference_kind": site["stop_kind"], "extreme_left_lane_id": site["left_lane_id"],
            "first_entry_frame": None if first_entry is None else measurements[first_entry]["frame"],
            "first_pre_entry_stop_frame": None if not stops else stops[0]["frame"],
            "red_conflict_entry_frames": [x["frame"] for x in conflict_entry],
            "legal_judgment": "unresolved", "physical_acceptance_claimed": False}
