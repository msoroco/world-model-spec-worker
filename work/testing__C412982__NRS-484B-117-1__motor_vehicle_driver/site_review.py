"""Gate an original site/vehicle/operator packet before a physical delivery run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sidewalk_measure import polygon


ROLES = ("jurisdiction", "map", "curb_or_highway_lateral_line",
         "property_line", "pedestrian_purpose", "sidewalk_polygon",
         "permanent_driveway", "temporary_driveway", "alley_entrance",
         "approach_route", "vehicle_blueprint_and_power", "wheel_design",
         "emergency_authorization", "law_officer_authority_and_duty",
         "security_guard_authority_and_duty", "operator_identity")
KINDS = ("permanent_driveway", "temporary_driveway", "alley_entrance")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reviewed_site(path, case_id):
    path = Path(path).resolve()
    site = json.loads(path.read_text(encoding="utf-8"))
    if (site.get("format") != "c412982-reviewed-original-sidewalk-v1" or
            site.get("source_kind") != "original_reviewed" or
            site.get("diagnostic_fixture") is not False or
            site.get("case_id") != case_id or not site.get("reviewer")):
        raise ValueError("reviewed original sidewalk packet identity missing")
    sources = site.get("sources")
    if not isinstance(sources, dict):
        raise ValueError("reviewed original source inventory missing")
    for role in ROLES:
        item = sources.get(role)
        if not isinstance(item, dict) or not item.get("path") or not item.get("sha256"):
            raise ValueError("reviewed original source missing: " + role)
        candidate = path.parent / item["path"]
        source = candidate.resolve()
        if (candidate.is_symlink() or not source.is_relative_to(path.parent) or
                not source.is_file() or sha(source) != item["sha256"]):
            raise ValueError("reviewed original source invalid: " + role)
        if site.get(role + "_source_sha256") != item["sha256"]:
            raise ValueError("original site/source binding differs: " + role)
    if not site.get("map_id") or not site.get("vehicle_blueprint_id"):
        raise ValueError("reviewed map and vehicle identity required")
    polygon(site.get("sidewalk_area_polygon_xy"))
    entrances = site.get("entrance_polygons_xy")
    if not isinstance(entrances, dict) or set(entrances) != set(KINDS):
        raise ValueError("all reviewed entrance geometries required")
    for kind in KINDS:
        polygon(entrances[kind])
    route = site.get("approach_route_xy")
    if not isinstance(route, list) or len(route) < 2:
        raise ValueError("reviewed approach route missing")
    if site.get("sidewalk_area_id") is None or site.get("pedestrian_purpose") is not True:
        raise ValueError("reviewed sidewalk identity and purpose missing")
    if site.get("body_geometry_source_sha256") != sources["vehicle_blueprint_and_power"]["sha256"]:
        raise ValueError("original body geometry source binding differs")
    design = site.get("vehicle_design")
    if not isinstance(design, dict) or design.get("power") not in ("combustion", "solely_electric"):
        raise ValueError("original vehicle power source unresolved")
    if design.get("wheel_count") not in (3, 4) or not isinstance(design.get("designed_for_wheel_count"), int):
        raise ValueError("original wheel design source unresolved")
    operator = site.get("operator_context")
    if not isinstance(operator, dict) or operator.get("role") not in ("ordinary", "emergency", "law_officer", "security_guard"):
        raise ValueError("original operator role source unresolved")
    if not operator.get("identity") or not operator.get("duty_period"):
        raise ValueError("original operator identity or duty period missing")
    return site
