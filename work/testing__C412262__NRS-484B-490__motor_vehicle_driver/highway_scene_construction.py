"""Original-source-gated Native setup for the C412262 narrow-highway parking plan."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from highway_observations import point


ASSIGNMENT = "testing__C412262__NRS-484B-490__motor_vehicle_driver"
SOURCE_FIELDS = ("map_sha256", "dedication_sha256", "boundary_sha256", "public_access_sha256",
                 "width_survey_sha256", "device_erection_sha256", "device_authority_sha256",
                 "device_content_sha256", "device_conformity_sha256", "device_extent_sha256",
                 "activity_source_sha256")


def load_case(case_id: str) -> dict:
    plan = json.loads((Path(__file__).resolve().parent / "case-plan.json").read_text())
    case = next((item for item in plan["cases"] if item["case_id"] == case_id), None)
    if case is None or not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("unknown exact narrow-highway parking case")
    return case


def validate_site(path: str | Path, case_id: str) -> dict:
    case = load_case(case_id)
    source_path = Path(path).resolve()
    raw = source_path.read_bytes()
    site = json.loads(raw)
    if (site.get("assignment_id") != ASSIGNMENT or site.get("cell_id") != "C412262" or
            site.get("source_kind") != "original_reviewed_highway_site" or
            site.get("review_status") != "reviewed"):
        raise ValueError("reviewed original highway site identity required")
    for field in SOURCE_FIELDS:
        value = site.get(field)
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("reviewed original source hash required: " + field)
        record = site.get("source_records", {}).get(field)
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            raise ValueError("reviewed original source record required: " + field)
        relative = Path(record["path"])
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError("reviewed original source path escapes site: " + field)
        unresolved = source_path.parent / relative
        target = unresolved.resolve()
        if (source_path.parent not in target.parents or unresolved.is_symlink() or
                not target.is_file() or record.get("sha256") != value or
                hashlib.sha256(target.read_bytes()).hexdigest() != value):
            raise ValueError("reviewed original source bytes changed: " + field)
    for key, expected in (("highway_width_variant", case["highway_width_request"]),
                          ("device_variant", case["device_request"]),
                          ("parking_location_variant", case["parking_location_request"])):
        if site.get(key) != expected:
            raise ValueError("reviewed site differs from exact case: " + key)
    for key in ("highway_boundary_xy_m", "device_extent_xy_m"):
        vertices = site.get(key)
        if not isinstance(vertices, list) or len(vertices) < 3:
            raise ValueError("reviewed full polygon required: " + key)
        for vertex in vertices:
            point(vertex)
    profile = site.get("full_highway_width_profile_m")
    if not isinstance(profile, list) or len(profile) < 2 or any(not isinstance(x, (int, float)) or x <= 0 for x in profile):
        raise ValueError("reviewed full highway width profile required")
    route = site.get("lane_route_xy_m")
    if not isinstance(route, list) or len(route) < 2:
        raise ValueError("reviewed lane route required")
    for vertex in route:
        point(vertex)
    device = site.get("device")
    if not isinstance(device, dict):
        raise ValueError("reviewed traffic-control device survey required")
    if case["device_request"] != "absent":
        for key in ("blueprint_id", "exact_instruction_text", "erecting_authority_id",
                    "conformity_source_id", "governing_extent_id"):
            if not isinstance(device.get(key), str) or not device[key]:
                raise ValueError("reviewed device field required: " + key)
    site["_source_sha256"] = hashlib.sha256(raw).hexdigest()
    return site


def construct(adapter, site_path: str | Path, case_id: str) -> dict:
    case = load_case(case_id)
    site = validate_site(site_path, case_id)
    owned = []
    try:
        adapter.configure_highway(site["lane_route_xy_m"], site["highway_boundary_xy_m"],
                                  site["full_highway_width_profile_m"])
        highway = adapter.read_highway()
        if not isinstance(highway, dict) or highway.get("boundary_xy_m") != site["highway_boundary_xy_m"]:
            raise ValueError("Native highway boundary readback differs")
        if highway.get("width_profile_m") != site["full_highway_width_profile_m"]:
            raise ValueError("Native full highway width readback differs")
        if case["device_request"] != "absent":
            device = adapter.spawn_device(site["device"])
            if not device:
                raise ValueError("prohibitory traffic-control device spawn failed")
            owned.append(device)
        observed_device = adapter.read_device()
        if not isinstance(observed_device, dict) or observed_device.get("state") != site["device_variant"]:
            raise ValueError("Native device erection and extent readback differs")
        if case["device_request"] != "absent":
            for key in ("exact_instruction_text", "erecting_authority_id", "conformity_source_id",
                        "governing_extent_id"):
                if observed_device.get(key) != site["device"][key]:
                    raise ValueError("Native device authority or content readback differs: " + key)
        vehicle = adapter.spawn_vehicle(site["lane_route_xy_m"][0])
        if not vehicle:
            raise ValueError("subject vehicle spawn failed")
        owned.append(vehicle)
        adapter.drive_to_parking_location(vehicle, case["parking_location_request"], site["lane_route_xy_m"])
        adapter.hold_for_activity(vehicle, case["activity_request"])
        observed_vehicle = adapter.read_vehicle_state(vehicle)
        if not isinstance(observed_vehicle, dict) or observed_vehicle.get("activity_request") != case["activity_request"]:
            raise ValueError("Native vehicle activity readback differs")
        return {"case_id": case_id, "site_source_sha256": site["_source_sha256"],
                "owned": tuple(owned), "physical_limit": "Original highway geometry, device pixels and actual parking activity require post-capture review."}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise
