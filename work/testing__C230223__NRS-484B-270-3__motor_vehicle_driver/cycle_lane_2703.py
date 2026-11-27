"""Source-gated construction for NRS 484B.270(3).

Requests are scenario targets. Only original Native frames can establish that an
actor occupied the designated facility or that one road user preceded another.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT = "testing__C230223__NRS-484B-270-3__motor_vehicle_driver"
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
ROAD_USERS = ("bicycle", "electric_bicycle", "electric_scooter",
              "qualified_pedestrian", "unqualified_pedestrian")
EXCEPTIONS = ("none", "alley_enter", "alley_exit", "driveway_enter",
              "driveway_exit", "disabled_vehicle", "avoid_conflict",
              "official_duties", "police_direction", "emergency")


def _point(value):
    if (not isinstance(value, (list, tuple)) or len(value) != 2 or
            any(isinstance(v, bool) or not isinstance(v, (float, int)) or
                not math.isfinite(v) for v in value)):
        raise ValueError("finite two-dimensional original site point required")
    return tuple(float(v) for v in value)


def _polygon(value):
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        raise ValueError("source polygon needs three vertices")
    points = [_point(p) for p in value]
    twice_area = sum(a[0] * b[1] - b[0] * a[1]
                     for a, b in zip(points, points[1:] + points[:1]))
    if abs(twice_area) < 1e-8:
        raise ValueError("source polygon is degenerate")
    return points


def inside(point, polygon):
    x, y = _point(list(point))
    vertices = _polygon([list(p) for p in polygon])
    inside_region = False
    for a, b in zip(vertices, vertices[1:] + vertices[:1]):
        if (a[1] > y) != (b[1] > y):
            intercept = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if x < intercept:
                inside_region = not inside_region
    return inside_region


def intersects(body, region):
    """Polygon overlap including crossed edges, not a center-point proxy."""
    a, b = _polygon(body), _polygon(region)
    if any(inside(p, b) for p in a) or any(inside(p, a) for p in b):
        return True

    def cross(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    for p, q in zip(a, a[1:] + a[:1]):
        for r, s in zip(b, b[1:] + b[:1]):
            if cross(p, q, r) * cross(p, q, s) < 0 and cross(r, s, p) * cross(r, s, q) < 0:
                return True
    return False


def _read(path, sha256, kind):
    path = Path(path)
    if (path.is_symlink() or not path.is_file() or
            not isinstance(sha256, str) or len(sha256) != 64 or
            hashlib.sha256(path.read_bytes()).hexdigest() != sha256):
        raise ValueError("reviewed " + kind + " source missing or changed")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("source_kind") != "original_reviewed":
        raise ValueError("reviewed " + kind + " source required")
    return value


def prepare(case_id, site_path, site_sha256, participant_path,
            participant_sha256, context_path, context_sha256):
    """Construct a target only from independently reviewed site/actor/context."""
    folder = Path(__file__).resolve().parent
    plan = json.loads((folder / "case-plan.json").read_text())
    cases = {case["case_id"]: case for case in plan["cases"]}
    if case_id not in cases or not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("exact case identity required")
    case = cases[case_id]
    site = _read(site_path, site_sha256, "site")
    participant = _read(participant_path, participant_sha256, "participant")
    context = _read(context_path, context_sha256, "context")
    if (site.get("assignment_id") != ASSIGNMENT or not site.get("map_id") or
            not site.get("facility_id") or not site.get("designation_authority") or
            site.get("facility_designated_for") not in
            ("bicycle", "electric_bicycle", "electric_scooter", "mixed_cycle") or
            not site.get("facility_extent_source")):
        raise ValueError("original designated cycle facility and extent required")
    facility = _polygon(site.get("facility_polygon"))
    conflict = _polygon(site.get("conflict_polygon"))
    routes = site.get("routes", {})
    route_name = case["case_slug"]
    route = routes.get(route_name)
    if not isinstance(route, dict):
        raise ValueError("exact source route required")
    ego_route = [_point(p) for p in route.get("ego", [])]
    other_route = [_point(p) for p in route.get("participant", [])]
    if len(ego_route) < 2 or len(other_route) < 2:
        raise ValueError("source routes need two or more points")
    if not any(inside(p, conflict) for p in other_route):
        raise ValueError("participant route misses conflict region")
    if not any(inside(p, facility) for p in other_route):
        raise ValueError("participant route misses designated facility")
    if participant.get("road_user_kind") != case["road_user_kind"]:
        raise ValueError("participant class differs from exact case")
    if (not participant.get("actor_blueprint_id") or
            not participant.get("identity_review") or
            not participant.get("body_measurement_method")):
        raise ValueError("distinct participant identity and body source required")
    if case["road_user_kind"].endswith("pedestrian"):
        facts = context.get("nrs_484b_297_6", {})
        qualified = all(facts.get(name) is True for name in
                        ("sidewalk_obstruction", "adjacent_strip_impassable",
                         "immediately_adjacent_highway", "near_side_route",
                         "return_when_practicable"))
        if qualified != (case["road_user_kind"] == "qualified_pedestrian"):
            raise ValueError("pedestrian statutory qualification differs from source")
    if (context.get("exception_kind") != case["exception_request"] or
            not context.get("exception_source_review") or
            context.get("law_id") != "NRS-484B-270-3"):
        raise ValueError("independent exception circumstance source required")
    if case["exception_request"] in ("alley_enter", "alley_exit", "driveway_enter", "driveway_exit"):
        if not route.get("junction_geometry_id") or not context.get("junction_kind"):
            raise ValueError("alley or driveway physical junction required")
        if context["junction_kind"] != case["exception_request"].split("_")[0]:
            raise ValueError("junction class differs from exception")
    return {"format": "cycle-lane-2703-native-plan-v1", "case_id": case_id,
            "map_id": site["map_id"], "facility_id": site["facility_id"],
            "facility_polygon": site["facility_polygon"],
            "conflict_polygon": site["conflict_polygon"],
            "ego_route": route["ego"], "participant_route": route["participant"],
            "ego_lane_action_request": case["ego_lane_action_request"],
            "ego_precedence_request": case["ego_precedence_request"],
            "exception_request": case["exception_request"],
            "participant_blueprint_id": participant["actor_blueprint_id"],
            "participant_kind": case["road_user_kind"],
            "source_sha256": {"site": site_sha256, "participant": participant_sha256,
                              "context": context_sha256},
            "capture_profile": {"hz": 20, "duration_s": 45, "views": list(VIEWS)},
            "physical_acceptance_claimed": False}


def measure_original_frames(rows, facility, conflict, ego_id, participant_id):
    """Recompute body occupancy and precedence from original 20 Hz frames."""
    if not isinstance(rows, list) or len(rows) != 900 or ego_id == participant_id:
        raise ValueError("900 distinct-actor original frames required")
    facility, conflict = _polygon(facility), _polygon(conflict)
    first_frame = rows[0].get("frame")
    first_time = rows[0].get("time_s")
    if not isinstance(first_frame, int) or isinstance(first_frame, bool):
        raise ValueError("original frame identity required")
    ego_hits = []
    participant_hits = []
    ego_conflict = []
    participant_conflict = []
    for i, row in enumerate(rows):
        if (row.get("frame") != first_frame + i or
                not isinstance(row.get("time_s"), (float, int)) or
                abs(row["time_s"] - first_time - i / 20) > 0.001 or
                row.get("ego_actor_id") != ego_id or
                row.get("participant_actor_id") != participant_id):
            raise ValueError("original 20 Hz actor/frame join broken")
        ego = _polygon(row.get("ego_body_polygon"))
        other = _polygon(row.get("participant_body_polygon"))
        ego_hits.append(intersects(ego, facility))
        participant_hits.append(intersects(other, facility))
        ego_conflict.append(intersects(ego, conflict))
        participant_conflict.append(intersects(other, conflict))
    if not any(participant_hits):
        raise ValueError("participant never occupied designated facility")
    first_ego = next((i for i, hit in enumerate(ego_conflict) if hit), None)
    first_other = next((i for i, hit in enumerate(participant_conflict) if hit), None)
    if first_ego is None or first_other is None:
        raise ValueError("both actors must approach the conflict region")
    return {"format": "cycle-lane-2703-original-measurement-v1",
            "frame_count": 900, "ego_facility_frames": sum(ego_hits),
            "participant_facility_frames": sum(participant_hits),
            "ego_conflict_entry_frame": first_frame + first_ego,
            "participant_conflict_entry_frame": first_frame + first_other,
            "observed_precedence": ("ego_first" if first_ego < first_other else
                                    "participant_first" if first_other < first_ego else
                                    "same_frame_unresolved"),
            "physical_acceptance_claimed": False}
