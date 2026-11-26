"""Source-gated Native construction calls for the nine one-way side controls."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from one_way_side_observations import polyline

ASSIGNMENT = "testing__C412262__NRS-484B-493__motor_vehicle_driver"


def _hash(value, name):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("original reviewed source hash required: " + name)


def load_case(case_id: str) -> dict:
    plan = json.loads((Path(__file__).resolve().parent / "case-plan.json").read_text())
    case = next((entry for entry in plan["cases"] if entry["case_id"] == case_id), None)
    if case is None or not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("unknown exact one-way parking case")
    return case


def validate_site(path: str | Path, case_id: str) -> dict:
    case = load_case(case_id)
    raw = Path(path).read_bytes()
    site = json.loads(raw)
    if (site.get("assignment_id") != ASSIGNMENT or site.get("cell_id") != "C412262" or
            site.get("source_kind") != "original_reviewed_street_survey" or
            site.get("review_status") != "reviewed"):
        raise ValueError("original reviewed street site and assignment required")
    for name in ("map_sha256", "street_status_sha256", "one_way_order_sha256", "street_boundary_sha256",
                 "permitted_direction_sha256", "device_erection_sha256",
                 "device_authority_sha256", "device_content_sha256", "device_extent_sha256"):
        _hash(site.get(name), name)
        records = site.get("source_records")
        record = records.get(name) if isinstance(records, dict) else None
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            raise ValueError("reviewed original source record required: " + name)
        relative = Path(record["path"])
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError("reviewed original source path escapes site: " + name)
        site_dir = Path(path).resolve().parent
        unresolved = site_dir / relative
        target = unresolved.resolve()
        if (site_dir not in target.parents or unresolved.is_symlink() or
                not target.is_file() or
                hashlib.sha256(target.read_bytes()).hexdigest() != site[name] or
                record.get("sha256") != site[name]):
            raise ValueError("reviewed original source bytes changed: " + name)
    if site.get("street_direction_variant") != case["street_direction_request"]:
        raise ValueError("reviewed street-direction variant differs from case")
    if site.get("notice_variant") != case["notice_request"]:
        raise ValueError("reviewed notice variant differs from case")
    polyline(site.get("lane_route_xy_m"))
    if not isinstance(site.get("notice_device"), dict):
        raise ValueError("reviewed official notice-device survey required")
    if site["notice_variant"] != "absent":
        device = site["notice_device"]
        for name in ("blueprint_id", "exact_notice_text", "erecting_authority_id",
                     "governing_extent_id"):
            if not isinstance(device.get(name), str) or not device[name]:
                raise ValueError("reviewed notice-device field required: " + name)
    site["_source_sha256"] = hashlib.sha256(raw).hexdigest()
    return site


def construct(adapter, site_path: str | Path, case_id: str) -> dict:
    case = load_case(case_id)
    site = validate_site(site_path, case_id)
    owned = []
    try:
        adapter.configure_street(site["street_direction_variant"], site["lane_route_xy_m"])
        if adapter.read_street_direction() != site["street_direction_variant"]:
            raise ValueError("Native street direction differs from reviewed site")
        if site["notice_variant"] != "absent":
            device = adapter.spawn_notice_device(site["notice_device"])
            if not device:
                raise ValueError("official notice-device spawn failed")
            owned.append(device)
        observed_notice = adapter.read_notice()
        if not isinstance(observed_notice, dict) or observed_notice.get("state") != site["notice_variant"]:
            raise ValueError("Native notice erection or extent readback differs")
        if site["notice_variant"] != "absent":
            for key in ("exact_notice_text", "erecting_authority_id", "governing_extent_id"):
                if observed_notice.get(key) != site["notice_device"][key]:
                    raise ValueError("Native notice content or authority readback differs: " + key)
        vehicle = adapter.spawn_vehicle(site["lane_route_xy_m"][0])
        if not vehicle:
            raise ValueError("subject vehicle spawn failed")
        owned.append(vehicle)
        adapter.drive_to_side(vehicle, case["vehicle_side_request"], site["lane_route_xy_m"])
        adapter.hold_for_activity(vehicle, case["activity_request"])
        observed = adapter.read_vehicle_state(vehicle)
        if not isinstance(observed, dict) or observed.get("activity_request") != case["activity_request"]:
            raise ValueError("Native vehicle activity readback differs")
        return {"case_id": case_id, "site_source_sha256": site["_source_sha256"],
                "owned": tuple(owned), "activity_request": case["activity_request"],
                "side_request": case["vehicle_side_request"],
                "physical_limit": "Original body geometry and activity purpose require post-capture review."}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise
