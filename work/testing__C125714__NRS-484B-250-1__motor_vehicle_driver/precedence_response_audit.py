"""Independent original-source audit of the yield versus advance pair."""
from __future__ import annotations

import json
import math
from pathlib import Path

from delivery_audit import audit_attempt


def rows(path, name):
    return [json.loads(line) for line in (Path(path) / name).read_text().splitlines()
            if line.strip()]


def center(row):
    vertices = row["body_vertices_xy_m"]
    if len(vertices) < 4:
        raise ValueError("original ego body lacks polygon vertices")
    return tuple(sum(float(vertex[axis]) for vertex in vertices) / len(vertices)
                 for axis in (0, 1))


def audit_response_pair(yield_attempt, advance_attempt, *, diagnostic=False):
    """Require controlled context, differing requests and realized ego progress.

    The 0.25 m motion separation is an engineering proof of distinct realized
    responses. It is not a statutory yield or danger threshold.
    """
    left = audit_attempt(yield_attempt, diagnostic=diagnostic)
    right = audit_attempt(advance_attempt, diagnostic=diagnostic)
    if left["site_review"]["original_map_sha256"] != right["site_review"]["original_map_sha256"]:
        raise ValueError("fixed original map changed")
    contexts = [json.loads((Path(path) / "intersection-context.json").read_text())
                for path in (yield_attempt, advance_attempt)]
    if (contexts[0]["crossing"] != contexts[1]["crossing"] or
            contexts[0]["law_context"] != contexts[1]["law_context"]):
        raise ValueError("fixed crossing or legal context changed")
    measurements = (left["measurements"], right["measurements"])
    if any(item["other_entered_before_ego"] is not True for item in measurements):
        raise ValueError("both response attempts need an other-first crossing")
    if measurements[0]["other_entry_frame"] != measurements[1]["other_entry_frame"]:
        raise ValueError("fixed other entry timing changed")
    bodies = [rows(path, "ego-body-history.jsonl") for path in (yield_attempt, advance_attempt)]
    controls = [rows(path, "controller-history.jsonl") for path in (yield_attempt, advance_attempt)]
    others = [rows(path, "other-body-history.jsonl") for path in (yield_attempt, advance_attempt)]
    n = len(bodies[0])
    if (n < 3 or any(len(group) != n for group in (*bodies, *controls, *others))):
        raise ValueError("pair lacks complete original frame series")
    for group in (*bodies, *controls, *others):
        if [item["frame"] for item in group] != [item["frame"] for item in bodies[0]]:
            raise ValueError("pair original frame join differs")
    if math.dist(center(bodies[0][0]), center(bodies[1][0])) > .1:
        raise ValueError("fixed initial ego body position changed")
    if math.dist(center(others[0][0]), center(others[1][0])) > .1:
        raise ValueError("fixed initial other body position changed")
    crossing = contexts[0]["crossing"]["bounds_xy_m"]
    target = ((crossing[0] + crossing[2]) / 2, (crossing[1] + crossing[3]) / 2)
    initial = center(bodies[0][0])
    direction = (target[0] - initial[0], target[1] - initial[1])
    length = math.hypot(*direction)
    if length <= 0:
        raise ValueError("ego approach direction is undefined")
    direction = (direction[0] / length, direction[1] / length)
    def request(row):
        return row.get("ego_next_tick_request", {}).get("request")
    last_conflict = min(measurements[0]["other_exit_frame"],
                        measurements[1]["other_exit_frame"])
    divergent = [i for i in range(n - 1)
                 if bodies[0][i]["frame"] < last_conflict and
                 request(controls[0][i]) == "brake" and
                 request(controls[1][i]) == "proceed"]
    if not divergent:
        raise ValueError("yield/advance controller requests did not diverge before clearance")
    progress = []
    for i in range(n):
        left_xy, right_xy = center(bodies[0][i]), center(bodies[1][i])
        progress.append(sum((right_xy[axis] - left_xy[axis]) * direction[axis]
                            for axis in (0, 1)))
    realized = [(i, j, progress[j]) for i in divergent
                for j in range(i + 1, min(n, i + 6)) if progress[j] >= .25]
    if not realized:
        raise ValueError("controller-only response difference lacks realized ego progress")
    first = realized[0]
    return {"comparison_id": "crossing_precedence",
            "declared_differences": ["ego_response_request"],
            "request_divergence_frame": bodies[0][first[0]]["frame"],
            "realized_difference_frame": bodies[0][first[1]]["frame"],
            "realized_progress_difference_m": round(first[2], 6),
            "diagnostic_fixture": diagnostic,
            "legal_verdict_claimed": False}
