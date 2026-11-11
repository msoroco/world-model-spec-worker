"""Measure a T-intersection entry comparison from retained Native-shaped sources.

Highway continuity comes from the retained lane graph and explicit highway
identity, not a scenario flag saying that the subject road ends.
"""

from hashlib import sha256
import json
from math import hypot, isfinite
from pathlib import Path


def _read(path, label):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing required source: " + label)
    raw = path.read_bytes()
    if not raw:
        raise ValueError("Empty required source: " + label)
    try:
        return json.loads(raw), sha256(raw).hexdigest()
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Invalid required source: " + label) from error


def classify_approaches(topology):
    if not topology.get("highway_identity_source") or not topology.get("junction_id"):
        raise ValueError("Topology lacks highway identity or junction source")
    nodes = topology.get("lanes")
    if not isinstance(nodes, dict):
        raise ValueError("Topology lacks connected lane graph")
    selected = {}
    for role in ("subject", "other"):
        start = topology.get(role + "_approach_lane")
        if start not in nodes or nodes[start].get("junction_id") not in (None, topology["junction_id"]):
            raise ValueError("Selected approach does not enter the same junction")
        highway = nodes[start].get("highway_id")
        if not highway:
            raise ValueError("Approach lacks source-backed highway identity")
        outgoing = nodes[start].get("successors")
        if not isinstance(outgoing, list) or not outgoing:
            raise ValueError("Approach lacks a drivable junction successor")
        # Native maps commonly put one or more junction lanes between the
        # approach and the outgoing highway. Follow those lanes to the first
        # exterior lane rather than treating the junction waypoint as an exit.
        pending = list(outgoing)
        visited = set()
        exterior = []
        entered_junction = nodes[start].get("junction_id") == topology["junction_id"]
        while pending:
            successor = pending.pop()
            if successor not in nodes:
                raise ValueError("Lane successor is absent from topology")
            if successor in visited:
                continue
            visited.add(successor)
            lane = nodes[successor]
            if lane.get("junction_id") == topology["junction_id"]:
                entered_junction = True
                following = lane.get("successors")
                if not isinstance(following, list):
                    raise ValueError("Junction lane lacks source-backed successors")
                pending.extend(following)
            elif lane.get("junction_id") is None:
                if not entered_junction:
                    raise ValueError("Selected approach bypasses the same junction")
                exterior.append(successor)
            else:
                raise ValueError("Approach successor enters another junction")
        if not entered_junction or not exterior:
            raise ValueError("Approach has no source-backed exit beyond junction")
        same_highway_out = [successor for successor in exterior
                            if nodes[successor].get("highway_id") == highway]
        selected[role] = {"approach_lane": start, "highway_id": highway,
                          "continues_beyond_junction": bool(same_highway_out),
                          "successors": outgoing, "exterior_lanes": sorted(exterior)}
    if selected["subject"]["continues_beyond_junction"]:
        raise ValueError("Subject highway does not end at the junction")
    if not selected["other"]["continues_beyond_junction"]:
        raise ValueError("Other highway is not through at the junction")
    if selected["subject"]["highway_id"] == selected["other"]["highway_id"]:
        raise ValueError("Ending and through approaches share one highway identity")
    return selected


def _polygon(value, label):
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError("Missing original polygon: " + label)
    polygon = [(float(x), float(y)) for x, y in value]
    if any(not (isfinite(x) and isfinite(y)) for x, y in polygon):
        raise ValueError("Nonfinite original polygon: " + label)
    return polygon


def _overlap(a, b):
    """Convex-polygon separation test, including oriented Native body boxes."""
    for polygon in (a, b):
        for start, end in zip(polygon, polygon[1:] + polygon[:1]):
            dx, dy = end[0] - start[0], end[1] - start[1]
            if hypot(dx, dy) < 1e-6:
                raise ValueError("Degenerate original polygon edge")
            axis = -dy, dx
            left = [x * axis[0] + y * axis[1] for x, y in a]
            right = [x * axis[0] + y * axis[1] for x, y in b]
            if max(left) < min(right) or max(right) < min(left):
                return False
    return True


def measure(topology_path, frames_path):
    topology, topology_hash = _read(topology_path, "intersection_topology.json")
    roles = classify_approaches(topology)
    path = Path(frames_path)
    if not path.is_file():
        raise ValueError("Missing required source: intersection_participants.jsonl")
    raw = path.read_bytes()
    if not raw:
        raise ValueError("Empty required source: intersection_participants.jsonl")
    try:
        rows = [json.loads(line) for line in raw.splitlines()]
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Invalid original intersection frames") from error
    if len(rows) < 3:
        raise ValueError("Intersection comparison needs approach, entry and exit frames")
    zone = _polygon(topology.get("conflict_polygon_xy"), "intersection conflict zone")
    subject_id, other_id = topology.get("subject_id"), topology.get("other_id")
    if not subject_id or not other_id or subject_id == other_id:
        raise ValueError("Topology lacks two distinct participant IDs")
    observations = []
    previous = None
    for row in rows:
        frame, time_s = row.get("frame"), row.get("time_s")
        if type(frame) is not int or type(time_s) not in (int, float):
            raise ValueError("Original frame/time identity missing")
        if not isfinite(time_s):
            raise ValueError("Nonfinite original intersection time")
        if previous is not None and (frame != previous[0] + 1 or
                                     abs(time_s - previous[1] - .05) > 1e-4):
            raise ValueError("Intersection original frames are not joined at 20 Hz")
        previous = frame, time_s
        if row.get("subject_id") != subject_id or row.get("other_id") != other_id:
            raise ValueError("Intersection participant identity changed")
        subject = _polygon(row.get("subject_corners"), "subject body")
        other = _polygon(row.get("other_corners"), "other body")
        observations.append({"frame": frame, "time_s": time_s,
                             "subject_in_conflict": _overlap(subject, zone),
                             "other_in_conflict": _overlap(other, zone)})
    def span(key):
        active = [r for r in observations if r[key]]
        if not active:
            raise ValueError("Participant never enters the intersection conflict zone: " + key)
        return active[0]["time_s"], active[-1]["time_s"], active[0]["frame"]
    subject_enter, subject_last, subject_frame = span("subject_in_conflict")
    other_enter, other_last, other_frame = span("other_in_conflict")
    return {"format": "worker-ending-road-observation", "topology_sha256": topology_hash,
            "frames_sha256": sha256(raw).hexdigest(), "approaches": roles,
            "subject_entry_frame": subject_frame, "other_entry_frame": other_frame,
            "entry_delta_s": subject_enter - other_enter,
            "subject_entered_after_other_last_conflict_frame": subject_enter > other_last,
            "conflict_overlap_observed": any(r["subject_in_conflict"] and r["other_in_conflict"]
                                             for r in observations),
            "observations": observations,
            "approximately_same_time_legal_judgment": None,
            "yield_right_of_way_legal_judgment": None}
