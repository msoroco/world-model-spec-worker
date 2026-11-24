"""Bind reviewed road status and all entrance devices to Native site readback.

This builds a source packet for capture. It does not decide proper sign erection,
actual officer authority, immediate hazard, or statutory compliance.
"""

import hashlib
import json
from pathlib import Path

from yield_site import ROAD, ROAD_OTHER_STOP, validate_authored_site
from yield_stage import Stage

ENTRANCES = (158208, 158212, 158214)


def build(stage: Stage, native_site, review_path):
    review_path = Path(review_path)
    if not review_path.is_file():
        raise ValueError("Missing reviewed signed-intersection status source")
    review = json.loads(review_path.read_text())
    map_path = ROAD_OTHER_STOP if stage.other_stop_sign else ROAD
    authored = validate_authored_site(map_path, other_stop=stage.other_stop_sign)
    if (review.get("authored_map_sha256") != authored["road_sha256"]
            or review.get("native_map_id") != native_site.get("native_map_id")
            or review.get("native_yield_sign_id") != native_site.get("native_yield_sign_id")
            or not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip()
            or not isinstance(review.get("road_status_source"), str)
            or not review["road_status_source"].strip()):
        raise ValueError("Status review differs from authored/Native source")
    if review.get("non_through_highway") is not True:
        raise ValueError("Non-through-highway status lacks affirmative source review")
    status_name = Path(review["road_status_source"])
    if status_name.is_absolute() or ".." in status_name.parts or not status_name.parts:
        raise ValueError("Road-status source path must stay in capture packet")
    status_file = review_path.parent / status_name
    if (not status_file.is_file() or not status_file.read_bytes()
            or hashlib.sha256(status_file.read_bytes()).hexdigest() != review.get("road_status_source_sha256")):
        raise ValueError("Missing or changed road-status source file")
    if review.get("traffic_signal_control") is not False:
        raise ValueError("Traffic signal exception must be sourced separately")
    if review.get("police_control") is not stage.officer_control_source_required:
        raise ValueError("Officer-control review differs from exact construction")
    devices = review.get("entrance_devices")
    expected = {"158208": "yield", "158212": "stop" if stage.other_stop_sign else "none",
                "158214": "none"}
    if devices != expected:
        raise ValueError("Reviewed device inventory differs from authored entrances")
    if stage.other_stop_sign and type(native_site.get("native_other_stop_sign_id")) is not int:
        raise ValueError("Missing Native other-entrance stop trigger")
    if not stage.other_stop_sign and native_site.get("native_other_stop_sign_id") is not None:
        raise ValueError("Unexpected Native other-entrance stop trigger")
    polygon = review.get("intersection_polygon_xy_m")
    if (not isinstance(polygon, list) or len(polygon) < 4
            or any(not isinstance(point, list) or len(point) != 2 for point in polygon)):
        raise ValueError("Missing source-reviewed intersection polygon")
    return {"case_id": stage.case_id, "native_map_id": native_site["native_map_id"],
            "intersection_id": native_site["intersection_id"],
            "ego_approach_road_id": 158208, "other_approach_road_id": 158212,
            "native_yield_sign_id": native_site["native_yield_sign_id"],
            "native_other_stop_sign_id": native_site.get("native_other_stop_sign_id"),
            "sign_governance_source": "authored-map-and-native-trigger-readback",
            "entrance_inventory_source": str(review_path.name),
            "yield_reference_source": "source-camera-site-review-pending",
            "highway_status_source": review["road_status_source"],
            "highway_status_source_sha256": review["road_status_source_sha256"],
            "status_review_sha256": hashlib.sha256(review_path.read_bytes()).hexdigest(),
            "authored_map_sha256": authored["road_sha256"],
            "non_through_highway": True,
            "police_control": stage.officer_control_source_required,
            "traffic_signal_control": False,
            "ego_entrance_device": "yield", "entrance_road_ids": list(ENTRANCES),
            "entrances": [{"road_id": road_id, "device": devices[str(road_id)]}
                          for road_id in ENTRANCES],
            "intersection_polygon_xy_m": polygon,
            "proper_sign_judgment": "unresolved",
            "road_status_judgment": "source_reviewed_pending_physical_confirmation"}
