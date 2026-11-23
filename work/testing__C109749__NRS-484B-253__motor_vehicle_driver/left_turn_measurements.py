"""Source-bound measurements for NRS 484B.253; no legal verdicts.

The caller supplies native body vertices and synchronized control histories.  A
requested controller state or a case name is never substituted for an observed
state.  Intersection boundaries must come from a reviewed map packet.
"""

from math import hypot


def _inside(point, polygon):
    if len(polygon) < 3:
        raise ValueError("intersection polygon needs at least three vertices")
    signs = []
    for start, end in zip(polygon, polygon[1:] + polygon[:1]):
        cross = (end[0] - start[0]) * (point[1] - start[1]) - (end[1] - start[1]) * (point[0] - start[0])
        if abs(cross) > 1e-8:
            signs.append(cross > 0)
    return bool(signs) and all(sign == signs[0] for sign in signs)


def body_occupancy(vertices, polygon):
    if len(vertices) != 8:
        raise ValueError("native vehicle body must have eight world vertices")
    points = [(float(v[0]), float(v[1])) for v in vertices]
    center = (sum(x for x, _ in points) / 8, sum(y for _, y in points) / 8)
    flags = [_inside(point, polygon) for point in points]
    return {"any_vertex_inside": any(flags), "center_inside": _inside(center, polygon), "full_body_inside": all(flags)}


def opposing_approach(ego_heading, other_heading):
    """Geometry diagnostic only; the reviewed road routes establish direction."""
    ex, ey = ego_heading
    ox, oy = other_heading
    en, on = hypot(ex, ey), hypot(ox, oy)
    if en <= 0 or on <= 0:
        raise ValueError("headings must be nonzero")
    return (ex * ox + ey * oy) / (en * on)


def measure(frames, polygon, *, source_id, map_sha256):
    if not source_id or len(map_sha256) != 64 or not frames:
        raise ValueError("original trace and source-hashed map are required")
    result = []
    previous_frame = -1
    for sample in frames:
        required = ("frame", "time_s", "ego_vertices", "opponent_vertices", "ego_heading",
                    "opponent_heading", "ego_speed_mps", "opponent_speed_mps", "ego_signal_left",
                    "ego_turn_committed", "opponent_cleared", "ego_braking")
        missing = [key for key in required if key not in sample]
        if missing:
            raise ValueError("missing original frame fields: " + ", ".join(missing))
        frame = int(sample["frame"])
        if frame <= previous_frame:
            raise ValueError("original frame order must increase")
        previous_frame = frame
        ego = body_occupancy(sample["ego_vertices"], polygon)
        opponent = body_occupancy(sample["opponent_vertices"], polygon)
        result.append({"frame": frame, "time_s": float(sample["time_s"]),
                       "ego": ego, "opponent": opponent,
                       "heading_cosine": opposing_approach(sample["ego_heading"], sample["opponent_heading"]),
                       "ego_speed_mps": float(sample["ego_speed_mps"]),
                       "opponent_speed_mps": float(sample["opponent_speed_mps"]),
                       "ego_signal_left": bool(sample["ego_signal_left"]),
                       "ego_turn_committed": bool(sample["ego_turn_committed"]),
                       "opponent_cleared": bool(sample["opponent_cleared"]),
                       "ego_braking": bool(sample["ego_braking"])})
    if not any(row["ego"]["full_body_inside"] for row in result):
        raise ValueError("no original frame establishes ego fully within intersection")
    return {"source_id": source_id, "map_sha256": map_sha256, "frames": result,
            "legal_judgment": "unresolved"}


def compare(left, right, *, changed_observables):
    """Reject absent or unchanged declared differences; do not infer right-of-way."""
    if left["map_sha256"] != right["map_sha256"]:
        raise ValueError("comparison map differs")
    if left["source_id"] == right["source_id"]:
        raise ValueError("comparison needs distinct original sources")
    if not changed_observables:
        raise ValueError("comparison needs a declared difference")
    first, second = left["frames"], right["frames"]
    if len(first) != len(second) or [r["frame"] for r in first] != [r["frame"] for r in second]:
        raise ValueError("comparison frame windows differ")
    if not any(a[key] != b[key] for key in changed_observables for a, b in zip(first, second)):
        raise ValueError("declared difference absent in original measurements")
    return {"sources": [left["source_id"], right["source_id"]],
            "changed_observables": list(changed_observables), "legal_judgment": "unresolved"}
