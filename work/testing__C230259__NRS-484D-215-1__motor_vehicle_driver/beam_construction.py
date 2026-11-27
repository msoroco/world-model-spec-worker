"""Source-gated Native construction plan and injected CARLA adapter contract."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from beam_measure import FEET_TO_METERS, VIEWS

ASSIGNMENT = "testing__C230259__NRS-484D-215-1__motor_vehicle_driver"
MODES = {"high", "low", "off"}


def _point(value: object, label: str) -> list[float]:
    if (not isinstance(value, list) or len(value) != 3 or
            any(type(x) not in (int, float) or not math.isfinite(x) for x in value)):
        raise ValueError("source-reviewed 3D point required: " + label)
    return [float(x) for x in value]


def _route(value: object, label: str) -> list[list[float]]:
    if not isinstance(value, list) or len(value) < 2:
        raise ValueError("source-reviewed route required: " + label)
    points = [_point(point, label) for point in value]
    if all(math.dist(points[i], points[i + 1]) < .01 for i in range(len(points) - 1)):
        raise ValueError("source-reviewed route has no motion: " + label)
    return points


def _polygon(value: object) -> list[list[float]]:
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError("reviewed traveled-highway/shoulder polygon required")
    points = []
    for point in value:
        if (not isinstance(point, list) or len(point) != 2 or
                any(type(x) not in (int, float) or not math.isfinite(x) for x in point)):
            raise ValueError("reviewed highway polygon coordinate invalid")
        points.append([float(x) for x in point])
    area = abs(sum(points[i][0] * points[(i + 1) % len(points)][1] -
                   points[(i + 1) % len(points)][0] * points[i][1]
                   for i in range(len(points))) / 2)
    if area < 1:
        raise ValueError("reviewed highway polygon degenerate")
    return points


def validate_site(packet_path: Path, case: dict, *, diagnostic: bool = False) -> dict:
    raw = Path(packet_path).read_bytes()
    site = json.loads(raw)
    if not case["case_id"].startswith(ASSIGNMENT + "__") or case.get("kind") != "delivery":
        raise ValueError("exact delivery case required")
    if (site.get("format") != "beam-road-site-v1" or
            site.get("case_id") != case["case_id"] or
            site.get("cell_id") != "C230259" or
            site.get("actor") != "motor_vehicle_driver" or
            site.get("diagnostic_fixture") is not diagnostic):
        raise ValueError("exact reviewed Native site identity differs")
    if not diagnostic:
        for field in ("source_reviewed", "nevada_highway_public_access_reviewed",
                      "lighting_time_source_reviewed", "lighting_time_qualifies",
                      "lamp_mounts_reviewed", "driver_eye_sources_reviewed",
                      "contour_and_load_reviewed", "roi_projection_reviewed"):
            if site.get(field) is not True:
                raise ValueError("missing source review: " + field)
    refs = site.get("source_refs")
    if not isinstance(refs, list) or not refs:
        raise ValueError("original map/time/vehicle source references required")
    for ref in refs:
        if not isinstance(ref, dict) or not ref.get("path") or len(ref.get("sha256", "")) != 64:
            raise ValueError("original source reference incomplete")
        source = Path(ref["path"])
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != ref["sha256"]:
            raise ValueError("original map/time/vehicle source hash differs")
    if not isinstance(site.get("map_name"), str) or len(site.get("map_sha256", "")) != 64:
        raise ValueError("reviewed Native map identity required")
    if site.get("requested_beam") != case["requested_beam"] or site["requested_beam"] not in MODES:
        raise ValueError("requested beam differs from exact case")
    if site.get("requested_contour") != case["requested_contour"] or site.get("requested_load") != case["requested_load"]:
        raise ValueError("contour/load comparison variable differs")
    if site.get("requested_start_body_gap_ft") != case["requested_start_body_gap_ft"]:
        raise ValueError("500-foot construction variable differs")
    routes = site.get("routes")
    if not isinstance(routes, dict) or set(routes) != {"ego", "oncoming"}:
        raise ValueError("ego and oncoming reviewed routes required")
    ego = _route(routes["ego"], "ego")
    oncoming = _route(routes["oncoming"], "oncoming")
    _polygon(site.get("highway_or_shoulder_polygon_xy_m"))
    ego_vector = [ego[-1][i] - ego[0][i] for i in range(2)]
    incoming_vector = [oncoming[-1][i] - oncoming[0][i] for i in range(2)]
    dot = sum(ego_vector[i] * incoming_vector[i] for i in range(2))
    if dot >= 0:
        raise ValueError("oncoming route must oppose ego route")
    targets = site.get("targets")
    if not isinstance(targets, dict) or set(targets) != {"person", "vehicle"}:
        raise ValueError("person and vehicle ahead required")
    for role in ("person", "vehicle"):
        _point(targets[role]["transform_m"], role)
        if not targets[role].get("blueprint_id"):
            raise ValueError("target blueprint required")
    if not isinstance(site.get("blueprints"), dict) or set(site["blueprints"]) != {"ego", "oncoming"}:
        raise ValueError("original motor vehicle blueprints required")
    for value in site["blueprints"].values():
        if not isinstance(value, str) or not value.startswith("vehicle."):
            raise ValueError("motor vehicle blueprint required")
    body_radii = site.get("reviewed_body_radii_m")
    if (not isinstance(body_radii, dict) or set(body_radii) != {"ego", "oncoming"} or
            any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0
                for value in body_radii.values())):
        raise ValueError("source-reviewed original vehicle body radii required")
    eye_offsets = site.get("driver_eye_offsets_m")
    if not isinstance(eye_offsets, dict) or set(eye_offsets) != {"ego", "oncoming"}:
        raise ValueError("source-reviewed driver-eye offsets required")
    for role, offset in eye_offsets.items():
        _point(offset, role + " driver eye offset")
    speeds = site.get("speed_requests_mps")
    if (not isinstance(speeds, dict) or set(speeds) != {"ego", "oncoming"} or
            any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0
                for value in speeds.values())):
        raise ValueError("positive motor vehicle speed requests required")
    cameras = site.get("cameras")
    if not isinstance(cameras, dict) or set(cameras) != set(VIEWS):
        raise ValueError("four reviewed camera poses required")
    for view, spec in cameras.items():
        if spec.get("blueprint_id") != "sensor.camera.rgb":
            raise ValueError("camera blueprint differs: " + view)
        _point(spec.get("transform_m"), view)
        fov = spec.get("fov_deg")
        if type(fov) not in (int, float) or not 1 <= fov <= 120:
            raise ValueError("reviewed camera field of view required: " + view)
    if not diagnostic and (len(site.get("camera_calibration_sha256", "")) != 64 or
                           len(site.get("projection_review_sha256", "")) != 64):
        raise ValueError("source-reviewed camera calibration and projection required")
    if case["branch"] == "oncoming":
        feet = case["requested_start_body_gap_ft"]
        if type(feet) not in (int, float) or feet <= 0:
            raise ValueError("oncoming start separation required")
        observed = (math.dist(ego[0], oncoming[0]) -
                    body_radii["ego"] - body_radii["oncoming"]) / FEET_TO_METERS
        if abs(observed - feet) > 10:
            raise ValueError("reviewed initial oncoming body separation differs from construction target")
    elif case["branch"] == "general":
        # Isolate the general illumination comparison from the special
        # within-500-foot oncoming condition for the entire reviewed route.
        start_gap_ft = (math.dist(ego[0], oncoming[0]) -
                        body_radii["ego"] - body_radii["oncoming"]) / FEET_TO_METERS
        if abs(start_gap_ft - case["requested_start_body_gap_ft"]) > 10:
            raise ValueError("general beam original start body gap differs")
        if min(math.dist(ego[0], oncoming[0]), math.dist(ego[-1], oncoming[-1])) - sum(body_radii.values()) <= 500 * FEET_TO_METERS + 10:
            raise ValueError("general beam case enters oncoming 500-foot condition")
    else:
        raise ValueError("unknown exact beam branch")
    return site


def construct(adapter, site: dict, *, case: dict) -> dict:
    """Execute a reviewed scene using a transaction-owned adapter.

    The adapter owns actor destruction and world-settings restoration even if a
    later sensor/actor spawn fails. The returned IDs are source identifiers,
    never an assertion that the requested physical light distribution occurred.
    """
    if site.get("case_id") != case["case_id"] or site.get("requested_beam") != case["requested_beam"]:
        raise ValueError("exact construction selection differs")
    actors = {}
    for role in ("ego", "oncoming"):
        actors[role] = adapter.spawn_vehicle(site["blueprints"][role], site["routes"][role][0])
        if actors[role] is None:
            raise ValueError("Native vehicle spawn failed: " + role)
        adapter.set_route(actors[role], site["routes"][role])
    for role in ("person", "vehicle"):
        target = site["targets"][role]
        actors[role] = adapter.spawn_target(target["blueprint_id"], target["transform_m"])
        if actors[role] is None:
            raise ValueError("Native target spawn failed: " + role)
    adapter.set_beam(actors["ego"], case["requested_beam"])
    cameras = {}
    for view, spec in site["cameras"].items():
        cameras[view] = adapter.spawn_camera(view, spec, attach_to=actors["ego"])
        if cameras[view] is None:
            raise ValueError("Native camera spawn failed: " + view)
    return {"actor_ids": {role: actor.id for role, actor in actors.items()},
            "camera_ids": {view: camera.id for view, camera in cameras.items()},
            "requested_beam": case["requested_beam"], "legal_judgment": None}
