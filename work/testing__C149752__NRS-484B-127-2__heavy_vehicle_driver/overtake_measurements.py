"""Source-bound physical passing sequence for NRS 484B.127(2).

The overtaking permission and conditions-permit qualifier remain legal review
questions. This module reports body ordering and lateral separation only.
"""

import hashlib
import json
import math
from pathlib import Path


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Missing finite " + name)
    return float(value)


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(root: Path) -> dict:
    root = Path(root)
    names = ("passing_history.jsonl", "road_context.json", "video_frames.jsonl")
    hashes = {}
    for name in names:
        path = root / name
        if not path.is_file():
            raise ValueError("Missing original source: " + name)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    context = json.loads((root / "road_context.json").read_text())
    for name in ("native_map_id", "highway_source", "lane_count_source", "road_id", "lane_forward_xy"):
        if name not in context or context[name] is None or context[name] == "":
            raise ValueError("Missing road context: " + name)
    count = context.get("same_direction_lane_count")
    if type(count) is not int or count < 1:
        raise ValueError("Invalid same-direction lane count")
    tangent = context["lane_forward_xy"]
    if not isinstance(tangent, list) or len(tangent) != 2:
        raise ValueError("Missing lane tangent")
    tx, ty = (_finite(v, "lane tangent") for v in tangent)
    norm = math.hypot(tx, ty)
    if norm == 0:
        raise ValueError("Zero lane tangent")
    tx, ty = tx/norm, ty/norm
    rows = _rows(root / "passing_history.jsonl")
    frames = _rows(root / "video_frames.jsonl")
    if len(rows) < 3 or len(rows) != len(frames):
        raise ValueError("Incomplete passing history")
    samples, prior = [], (-1, -math.inf)
    for index, (row, frame) in enumerate(zip(rows, frames)):
        fid, time = row.get("frame"), _finite(row.get("time_s"), "time")
        if type(fid) is not int or fid <= prior[0] or time <= prior[1]:
            raise ValueError("Nonmonotone original history")
        prior = fid, time
        if frame.get("video_frame") != index or frame.get("carla_frame") != fid or frame.get("time_s") != time:
            raise ValueError("Original video frame join failed")
        bodies = {}
        for role in ("ego", "lead"):
            body = row.get(role)
            if not isinstance(body, dict) or body.get("road_id") != context["road_id"]:
                raise ValueError("Participant road identity mismatch: " + role)
            if body.get("truck_or_combination") is not True:
                raise ValueError("Unqualified truck source: " + role)
            width = _finite(body.get("overall_width_m"), "truck width")
            if width < 80 * .0254:
                raise ValueError("Truck below statutory 80-inch width")
            vertices = body.get("body_vertices_xy_m")
            if not isinstance(vertices, list) or len(vertices) < 4:
                raise ValueError("Missing complete body: " + role)
            points = []
            for vertex in vertices:
                if not isinstance(vertex, list) or len(vertex) != 2:
                    raise ValueError("Invalid body vertex")
                x, y = (_finite(v, "body vertex") for v in vertex)
                points.append((x*tx+y*ty, -x*ty+y*tx))
            bodies[role] = {"along": [min(p[0] for p in points), max(p[0] for p in points)],
                            "lateral": [min(p[1] for p in points), max(p[1] for p in points)],
                            "lane_id": body.get("lane_id"), "width_m": width}
        ego, lead = bodies["ego"], bodies["lead"]
        behind = ego["along"][1] < lead["along"][0]
        ahead = ego["along"][0] > lead["along"][1]
        lateral_clearance = max(ego["lateral"][0]-lead["lateral"][1], lead["lateral"][0]-ego["lateral"][1])
        samples.append({"frame": fid, "time_s": time, "ego_behind": behind,
                        "ego_ahead": ahead, "lateral_body_clearance_m": lateral_clearance,
                        "ego_lane_id": ego["lane_id"], "lead_lane_id": lead["lane_id"]})
    first_behind = next((i for i, sample in enumerate(samples) if sample["ego_behind"]), None)
    first_ahead = next((i for i, sample in enumerate(samples) if first_behind is not None and i > first_behind and sample["ego_ahead"]), None)
    if first_ahead is None or not any(sample["lateral_body_clearance_m"] > 0 for sample in samples[first_behind+1:first_ahead]):
        raise ValueError("No sourced lateral pass from behind to ahead")
    return {"format": "worker-truck-overtake-observations", "sources": hashes,
            "same_direction_lane_count": count, "two_lane_exemption_observed": count >= 2,
            "first_behind_frame": samples[first_behind]["frame"],
            "first_ahead_frame": samples[first_ahead]["frame"], "samples": samples,
            "overtaking_exception_judgment": "unresolved", "conditions_permit_judgment": "unresolved",
            "safe_occupancy_judgment": "unresolved", "legal_conclusion": "unresolved"}


def analyze_following(root: Path) -> dict:
    """Measure every joined body gap; leave road and safety judgments open.

    The 1 mm band labels sampled equality at the precision of the diagnostic
    coordinates. It is a measurement tolerance, not a legal safe harbor.
    """
    root = Path(root)
    names = ("following_history.jsonl", "road_context.json", "video_frames.jsonl")
    sources = {}
    for name in names:
        path = root / name
        if not path.is_file():
            raise ValueError("Missing original source: " + name)
        sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    context = json.loads((root / "road_context.json").read_text())
    for name in ("native_map_id", "highway_source", "lane_count_source", "road_id", "lane_forward_xy"):
        if context.get(name) in (None, ""):
            raise ValueError("Missing road context: " + name)
    lane_count = context.get("same_direction_lane_count")
    if type(lane_count) is not int or lane_count < 1:
        raise ValueError("Invalid same-direction lane count")
    tangent = context["lane_forward_xy"]
    if not isinstance(tangent, list) or len(tangent) != 2:
        raise ValueError("Missing lane tangent")
    tx, ty = (_finite(v, "lane tangent") for v in tangent)
    length = math.hypot(tx, ty)
    if length == 0:
        raise ValueError("Zero lane tangent")
    tx, ty = tx / length, ty / length
    history = _rows(root / "following_history.jsonl")
    frames = _rows(root / "video_frames.jsonl")
    if len(history) < 3 or len(history) != len(frames):
        raise ValueError("Incomplete following history")
    observations = []
    identities = None
    previous = (-1, -math.inf)
    for index, (row, frame) in enumerate(zip(history, frames)):
        fid, time = row.get("frame"), _finite(row.get("time_s"), "time")
        if type(fid) is not int or fid <= previous[0] or time <= previous[1]:
            raise ValueError("Nonmonotone original history")
        if frame.get("video_frame") != index or frame.get("carla_frame") != fid or frame.get("time_s") != time:
            raise ValueError("Original video frame join failed")
        if index and abs(time - previous[1] - .05) > .01:
            raise ValueError("Missing 20 Hz following sample")
        previous = fid, time
        bodies = {}
        ids = []
        for role in ("ego", "lead"):
            body = row.get(role)
            if not isinstance(body, dict) or body.get("road_id") != context["road_id"]:
                raise ValueError("Participant road identity mismatch: " + role)
            actor_id = body.get("actor_id")
            if type(actor_id) is not int:
                raise ValueError("Missing participant actor ID: " + role)
            ids.append(actor_id)
            if body.get("truck_or_combination") is not True:
                raise ValueError("Unqualified truck source: " + role)
            width = _finite(body.get("overall_width_m"), "truck width")
            if width < 80 * .0254:
                raise ValueError("Truck below statutory 80-inch width")
            vertices = body.get("body_vertices_xy_m")
            if not isinstance(vertices, list) or len(vertices) < 4:
                raise ValueError("Missing complete body: " + role)
            projections = []
            for vertex in vertices:
                if not isinstance(vertex, list) or len(vertex) != 2:
                    raise ValueError("Invalid body vertex")
                x, y = (_finite(v, "body vertex") for v in vertex)
                projections.append((x * tx + y * ty, -x * ty + y * tx))
            lateral_width = max(p[1] for p in projections) - min(p[1] for p in projections)
            if abs(lateral_width - width) > .05:
                raise ValueError("Body width and declared width disagree: " + role)
            bodies[role] = (min(p[0] for p in projections), max(p[0] for p in projections), body.get("lane_id"))
        if ids[0] == ids[1] or (identities is not None and tuple(ids) != identities):
            raise ValueError("Participant actor identity changed")
        identities = tuple(ids)
        ego, lead = bodies["ego"], bodies["lead"]
        if ego[2] is None or ego[2] != lead[2]:
            raise ValueError("Participants are not in the same sourced lane")
        gap_m = lead[0] - ego[1]
        if gap_m < 0:
            raise ValueError("Subject body no longer follows lead body")
        delta_m = gap_m - 500 * .3048
        relation = "at_sampled_precision" if abs(delta_m) <= .001 else ("below" if delta_m < 0 else "above")
        observations.append({"frame": fid, "time_s": time, "body_gap_m": gap_m,
                             "body_gap_ft": gap_m / .3048, "delta_from_500_ft_m": delta_m,
                             "sample_relation": relation})
    return {"format": "worker-truck-following-observations", "sources": sources,
            "actor_ids": {"ego": identities[0], "lead": identities[1]},
            "same_direction_lane_count": lane_count,
            "two_lane_nonapplication_context": lane_count >= 2,
            "sampled_gap_min_m": min(o["body_gap_m"] for o in observations),
            "sampled_gap_max_m": max(o["body_gap_m"] for o in observations),
            "all_samples_at_or_above_500_ft": all(o["delta_from_500_ft_m"] >= -.001 for o in observations),
            "sample_precision_m": .001, "samples": observations,
            "between_sample_gap": "unresolved", "conditions_permit_judgment": "unresolved",
            "safe_occupancy_judgment": "unresolved", "legal_conclusion": "unresolved"}


def analyze_width_boundary(root: Path, varied_role: str, expected_relation: str) -> dict:
    """Measure an 80-inch boundary case from retained original truck bodies.

    A below-width truck is a valid nonapplication observation. The 1 mm equality
    band describes source coordinate precision, not a new statutory tolerance.
    """
    if varied_role not in ("ego", "lead") or expected_relation not in ("below", "at", "above"):
        raise ValueError("Invalid width boundary case")
    root = Path(root)
    names = ("truck_history.jsonl", "road_context.json", "video_frames.jsonl")
    sources = {}
    for name in names:
        path = root / name
        if not path.is_file():
            raise ValueError("Missing original source: " + name)
        sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    context = json.loads((root / "road_context.json").read_text())
    tangent = context.get("lane_forward_xy")
    if not isinstance(tangent, list) or len(tangent) != 2:
        raise ValueError("Missing lane tangent")
    tx, ty = (_finite(value, "lane tangent") for value in tangent)
    length = math.hypot(tx, ty)
    if length == 0:
        raise ValueError("Zero lane tangent")
    tx, ty = tx / length, ty / length
    road_id, lane_id = context.get("road_id"), context.get("lane_id")
    if road_id is None or lane_id is None or not context.get("highway_source"):
        raise ValueError("Missing sourced road context")
    rows = _rows(root / "truck_history.jsonl")
    frames = _rows(root / "video_frames.jsonl")
    if len(rows) < 3 or len(rows) != len(frames):
        raise ValueError("Incomplete width history")
    threshold = 80 * .0254
    precision = .001
    identities = None
    previous = (-1, -math.inf)
    samples = []
    for index, (row, frame) in enumerate(zip(rows, frames)):
        fid = row.get("frame")
        time = _finite(row.get("time_s"), "time")
        if type(fid) is not int or fid <= previous[0] or time <= previous[1]:
            raise ValueError("Nonmonotone original width history")
        if index and abs(time - previous[1] - .05) > .01:
            raise ValueError("Missing 20 Hz width sample")
        if (frame.get("video_frame") != index or frame.get("carla_frame") != fid
                or frame.get("time_s") != time):
            raise ValueError("Original video frame join failed")
        previous = fid, time
        widths = {}
        ids = []
        for role in ("ego", "lead"):
            actor = row.get(role)
            if (not isinstance(actor, dict) or actor.get("is_truck_or_combination") is not True
                    or actor.get("road_id") != road_id or actor.get("lane_id") != lane_id):
                raise ValueError("Lost sourced truck and lane relation: " + role)
            actor_id = actor.get("actor_id")
            if type(actor_id) is not int:
                raise ValueError("Missing participant actor ID: " + role)
            ids.append(actor_id)
            width = _finite(actor.get("overall_width_m"), "overall width")
            vertices = actor.get("body_vertices_xy_m")
            if not isinstance(vertices, list) or len(vertices) < 4:
                raise ValueError("Missing complete body: " + role)
            lateral = []
            for vertex in vertices:
                if not isinstance(vertex, list) or len(vertex) != 2:
                    raise ValueError("Invalid body vertex")
                x, y = (_finite(value, "body vertex") for value in vertex)
                lateral.append(-x * ty + y * tx)
            if abs(max(lateral) - min(lateral) - width) > .05:
                raise ValueError("Body width and declared width disagree: " + role)
            widths[role] = width
        if ids[0] == ids[1] or (identities is not None and tuple(ids) != identities):
            raise ValueError("Participant actor identity changed")
        identities = tuple(ids)
        fixed_role = "lead" if varied_role == "ego" else "ego"
        if widths[fixed_role] < threshold - precision:
            raise ValueError("Fixed truck below 80-inch control")
        delta = widths[varied_role] - threshold
        relation = "at" if abs(delta) <= precision else ("below" if delta < 0 else "above")
        if relation != expected_relation:
            raise ValueError("Width boundary relation differs from exact case")
        samples.append({"frame": fid, "time_s": time, "widths_m": widths,
                        "delta_from_80in_m": delta, "sample_relation": relation})
    return {"format": "worker-truck-width-boundary-observations", "sources": sources,
            "actor_ids": {"ego": identities[0], "lead": identities[1]},
            "varied_role": varied_role, "expected_relation": expected_relation,
            "threshold_m": threshold, "sample_precision_m": precision, "samples": samples,
            "legal_truck_class": "unresolved", "legal_conclusion": "unresolved"}


def _inspect_saved_comparison(root: Path, suffix: str) -> dict:
    """Recompute comparison facts from retained originals, independent of the finalizer."""
    root = Path(root)
    config = json.loads((root / "config.json").read_text())
    result = json.loads((root / "result.json").read_text())
    report = json.loads((root / "analysis-report.json").read_text())
    road = json.loads((root / "road_context.json").read_text())
    if not config["selected_case_id"].endswith("__" + suffix) or result["case_id"] != config["selected_case_id"]:
        raise ValueError("Comparison case identity differs")
    history = _rows(root / "truck_history.jsonl")
    frames = _rows(root / "video_frames.jsonl")
    if not history or len(history) != len(frames):
        raise ValueError("Comparison original frame join differs")
    tangent = road["lane_forward_xy"]
    tx, ty = (_finite(v, "lane tangent") for v in tangent)
    norm = math.hypot(tx, ty)
    if norm <= 0:
        raise ValueError("Comparison lane tangent missing")
    tx, ty = tx / norm, ty / norm
    gaps, phases = [], []
    widths = {"ego": [], "lead": []}
    blueprints = {"ego": set(), "lead": set()}
    for index, (row, frame) in enumerate(zip(history, frames)):
        if (frame.get("video_frame") != index or frame.get("carla_frame") != row.get("frame")
                or frame.get("time_s") != row.get("time_s")):
            raise ValueError("Comparison original frame join differs")
        projected = {}
        for role in ("ego", "lead"):
            actor = row[role]
            allowed = {road["lane_id"], road.get("passing_lane_id")} if role == "ego" and suffix == "overtaking_pass" else {road["lane_id"]}
            if (not actor.get("is_truck_or_combination") or actor["road_id"] != road["road_id"]
                    or actor["lane_id"] not in allowed or len(actor["body_vertices_xy_m"]) < 4):
                raise ValueError("Comparison lost sourced truck road/lane relation")
            projected[role] = [x * tx + y * ty for x, y in actor["body_vertices_xy_m"]]
            widths[role].append(float(actor["overall_width_m"]))
            blueprints[role].add(actor["blueprint_id"])
        gap = min(projected["lead"]) - max(projected["ego"])
        gaps.append(gap)
        lane = row["ego"]["lane_id"]
        phases.append("following_behind" if lane == road["lane_id"] and gap > 0 else
                      "passing_behind" if lane == road.get("passing_lane_id") and gap > 0 else
                      "passing_ahead" if lane == road.get("passing_lane_id") and gap < 0 else
                      "returned_ahead" if lane == road["lane_id"] and gap < 0 else "ambiguous")
    measure = report["measurements"]["minimum_sampled_body_gap_m"]
    if not math.isclose(min(gaps), measure["value"], abs_tol=1e-6):
        raise ValueError("Comparison finalizer gap differs from original bodies")
    for name in ("truck_history.jsonl", "road_context.json", "video_frames.jsonl"):
        checksum = hashlib.sha256((root / name).read_bytes()).hexdigest()
        if measure["sources"].get(name) != checksum:
            raise ValueError("Comparison source hash differs: " + name)
    if suffix == "overtaking_pass" and report["measurements"]["overtaking_phase_sequence"]["value"] != phases:
        raise ValueError("Comparison passing phases differ from original bodies/lanes")
    if any(len(ids) != 1 for ids in blueprints.values()):
        raise ValueError("Comparison truck blueprint changed within case")
    return {"case_id": result["case_id"], "minimum_gap_m": min(gaps), "initial_gap_m": gaps[0],
            "phases": phases, "lane_count": road["same_direction_lane_count"],
            "road_id": road["road_id"], "lane_id": road["lane_id"],
            "widths_m": {role: min(values) for role, values in widths.items()},
            "blueprints": {role: next(iter(ids)) for role, ids in blueprints.items()},
            "rate_hz": config["rate_hz"], "duration_s": config["duration_s"],
            "cameras": config["cameras"], "required_atoms": config["required_atoms"]}


def audit_saved_comparisons(paths: dict) -> dict:
    """Audit the three selected controls from five exact saved diagnostics."""
    names = ("following_under_500_ft", "following_at_500_ft", "following_over_500_ft",
             "overtaking_pass", "two_lanes")
    if set(paths) != set(names):
        raise ValueError("Supply exactly five selected saved cases")
    facts = {name: _inspect_saved_comparison(paths[name], name) for name in names}
    under, at, over, passing, lanes = (facts[name] for name in names)
    fixed = ("widths_m", "blueprints", "rate_hz", "duration_s", "cameras", "required_atoms")
    for field in fixed:
        if any(facts[name][field] != under[field] for name in names[1:]):
            raise ValueError("Comparison changed fixed condition: " + field)
    if any(facts[name]["road_id"] != under["road_id"] for name in names[1:]):
        raise ValueError("Comparison changed sourced road")
    if any(facts[name]["lane_count"] != 1 for name in names[:4]) or lanes["lane_count"] != 2:
        raise ValueError("Comparison lane count contrast failed")
    measured = [under["minimum_gap_m"], at["minimum_gap_m"], over["minimum_gap_m"]]
    if not measured[0] < 152.4 or abs(measured[1] - 152.4) > .001 or measured[2] <= 152.4:
        raise ValueError("Comparison gap boundary ordering failed")
    if any(phase != "following_behind" for phase in under["phases"]):
        raise ValueError("Comparison following control changed passing state")
    sequence = ("following_behind", "passing_behind", "passing_ahead", "returned_ahead")
    cursor = 0
    for phase in sequence:
        while cursor < len(passing["phases"]) and passing["phases"][cursor] != phase:
            cursor += 1
        if cursor == len(passing["phases"]):
            raise ValueError("Comparison passing sequence omits " + phase)
        cursor += 1
    if abs(under["initial_gap_m"] - passing["initial_gap_m"]) > .05:
        raise ValueError("Comparison initial passing gap changed")
    if abs(under["minimum_gap_m"] - lanes["minimum_gap_m"]) > .05:
        raise ValueError("Comparison two-lane gap changed")
    return {"format": "worker-nrs-484b-127-2-saved-comparison-audit", "passed": True,
            "comparisons": {"following_gap_boundary": measured,
                            "overtaking_permission": passing["phases"],
                            "same_direction_lane_exclusion": [under["lane_count"], lanes["lane_count"]]},
            "case_ids": [facts[name]["case_id"] for name in names],
            "fixed_conditions": list(fixed),
            "scope": "synthetic saved-source software audit; Native, physical and legal status unresolved"}
