"""Source-gated same-lane pass and abreast construction.

The local operator supplies surveyed Native geometry and reviewed identity,
classification, consent, and exception sources. Synthetic packets cannot drive
an original capture.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


SOURCE_KEYS = (
    "map", "lane_geometry", "route_geometry", "ego_classification",
    "other_classification", "driver_identity", "driver_consent",
    "subsection_3_review",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _point(value):
    require(isinstance(value, (list, tuple)) and len(value) == 2 and
            all(isinstance(v, (int, float)) and not isinstance(v, bool) and
                math.isfinite(v) for v in value), "finite surveyed point required")
    return tuple(float(v) for v in value)


def reviewed_scene(path, case_id, parameters):
    path = Path(path).resolve()
    scene = json.loads(path.read_text(encoding="utf-8"))
    require(scene.get("format") == "c229023-reviewed-original-v1" and
            scene.get("source_kind") == "original_reviewed" and
            scene.get("diagnostic_fixture") is False,
            "original reviewed scene packet required")
    require(scene.get("case_id") == case_id and scene.get("reviewer"),
            "reviewed exact case identity required")
    require(scene.get("map_id") and scene.get("opendrive_sha256"),
            "reviewed original map required")
    sources = scene.get("sources", {})
    require(set(SOURCE_KEYS) <= set(sources), "reviewed source inventory incomplete")
    for key in SOURCE_KEYS:
        item = sources[key]
        require(item.get("path") and item.get("sha256"), "source missing: " + key)
        source = path.parent / item["path"]
        require(not source.is_symlink() and source.resolve().is_relative_to(path.parent)
                and source.is_file() and sha(source) == item["sha256"],
                "source hash or path invalid: " + key)
    require(scene.get("ego_blueprint_id") and scene.get("other_blueprint_id"),
            "reviewed participant blueprints required")
    require(scene.get("ego_vehicle_class") == "motorcycle" and
            scene.get("ego_classification_source_sha256") ==
            sources["ego_classification"]["sha256"],
            "reviewed Chapter 486 motorcycle classification required")
    require(scene.get("other_vehicle_class") in ("motorcycle", "moped", "motor_vehicle") and
            scene.get("other_classification_source_sha256") ==
            sources["other_classification"]["sha256"],
            "other vehicle classification requires source")
    require(scene.get("driver_identity_source_sha256") == sources["driver_identity"]["sha256"],
            "driver identity source differs")
    require(scene.get("consent_status") in ("consented", "not_consented", "unresolved") and
            scene.get("consent_source_sha256") == sources["driver_consent"]["sha256"],
            "independent driver consent source required")
    require(scene.get("subsection_3_status") in ("applies", "does_not_apply", "unresolved") and
            scene.get("subsection_3_source_sha256") == sources["subsection_3_review"]["sha256"],
            "subsection 3 review source required")
    if parameters["requested_driver_consent"]:
        require(scene["consent_status"] == "consented", "consented case needs independent consent")
    elif parameters["requested_two_wheeler_count"] > 1:
        require(scene["consent_status"] == "not_consented", "unconsented case needs independent absence source")
    require(scene["survey"].get("other_vehicle_class") == scene["other_vehicle_class"],
            "surveyed other vehicle class differs from reviewed classification")
    return construction(scene["survey"], parameters)


def construction(survey, parameters):
    """Return source-surveyed spawn/route requests; no legal clearance cutoff."""
    origin = _point(survey.get("route_origin_xy"))
    axis = _point(survey.get("route_unit_xy"))
    require(abs(math.hypot(*axis) - 1.0) < 0.01, "surveyed route axis must be unit length")
    width = survey.get("lane_width_m")
    require(isinstance(width, (int, float)) and 3.5 <= width <= 8,
            "surveyed shared lane width outside executable engineering envelope")
    same = parameters["requested_same_lane"]
    passing = parameters["requested_pass"]
    count = parameters["requested_two_wheeler_count"]
    require(count in (1, 2, 3), "reviewed rider count unsupported")
    if count > 1:
        require(survey.get("other_vehicle_class") in ("motorcycle", "moped"),
                "abreast case requires motorcycle or moped companions")
    lateral = survey.get("abreast_lateral_offsets_m")
    require(isinstance(lateral, list) and len(lateral) == 3 and
            all(isinstance(x, (float, int)) and math.isfinite(x) for x in lateral),
            "surveyed three-rider lateral offsets missing")
    require(max(lateral) - min(lateral) < width,
            "surveyed abreast riders do not fit in shared-lane envelope")
    half_widths = survey.get("participant_half_widths_m")
    require(isinstance(half_widths, list) and len(half_widths) == 3 and
            all(isinstance(x, (float, int)) and 0.2 < x < 1.2 for x in half_widths),
            "surveyed participant body widths required")
    used = (0, 1, 2) if count == 3 else (0, 1)
    if same:
        require(all(abs(lateral[i]) + half_widths[i] < width / 2 for i in used),
                "surveyed full rider footprint leaves shared traffic lane")
    if not passing:
        require(all(abs(lateral[i] - lateral[j]) >
                    half_widths[i] + half_widths[j] + 0.15
                    for i in used for j in used if i < j),
                "abreast body footprints overlap in engineering geometry")
    ego_lane = survey.get("ego_lane_id")
    other_lane = survey.get("other_lane_id")
    adjacent_lane = survey.get("adjacent_lane_id")
    require(all(isinstance(x, int) and x != 0 for x in (ego_lane, other_lane, adjacent_lane))
            and ego_lane == other_lane and adjacent_lane != ego_lane,
            "reviewed lane identity and adjacent control required")
    lane_id = ego_lane if same else adjacent_lane
    route_stations = survey.get("route_stations_m")
    require(isinstance(route_stations, list) and len(route_stations) >= 3 and
            all(isinstance(x, (float, int)) and math.isfinite(x) for x in route_stations) and
            all(a < b for a, b in zip(route_stations, route_stations[1:])),
            "monotone surveyed route stations required")
    perp = (-axis[1], axis[0])

    def point(station, offset):
        return (origin[0] + axis[0] * station + perp[0] * offset,
                origin[1] + axis[1] * station + perp[1] * offset)

    ego_offset = lateral[0] if same else survey.get("adjacent_lane_center_offset_m")
    require(isinstance(ego_offset, (int, float)) and math.isfinite(ego_offset),
            "adjacent-lane center offset missing")
    ego_start = route_stations[0] - (12 if passing else 0)
    other_start = route_stations[0] + (5 if passing else 0)
    participants = [
        {"role": "ego", "lane_id": lane_id, "station_m": ego_start,
         "lateral_m": ego_offset, "xy": point(ego_start, ego_offset)},
        {"role": "other", "lane_id": other_lane, "station_m": other_start,
         "lateral_m": lateral[1], "xy": point(other_start, lateral[1])},
    ]
    if count == 3:
        participants.append({"role": "third", "lane_id": other_lane,
                             "station_m": other_start, "lateral_m": lateral[2],
                             "xy": point(other_start, lateral[2])})
    if count == 2 and not passing:
        participants[0]["station_m"] = other_start
        participants[0]["xy"] = point(other_start, ego_offset)
    if count == 3:
        participants[0]["station_m"] = other_start
        participants[0]["xy"] = point(other_start, ego_offset)
    return {"participants": participants,
            "routes": {p["role"]: [point(s, p["lateral_m"]) for s in route_stations]
                       for p in participants},
            "lane_width_m": width, "route_origin_xy": origin,
            "route_unit_xy": axis,
            "review_limit": "Requested geometry is checked against original Native lane and actor readback; no statutory passing, clearance or duration threshold is inferred."}
