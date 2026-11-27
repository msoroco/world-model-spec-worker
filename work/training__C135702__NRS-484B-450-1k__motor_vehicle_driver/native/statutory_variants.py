"""Exact draft requests for the remaining 484B.450(1)(k) alternatives.

Requests are engineering constructions. Source records and Native readback must
establish what occurred; this module assigns no legal or physical outcome.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from branch_context import ACTIVITIES, EXCEPTIONS, checked_record, validate
from geometry import EXCAVATION, FRAME_COUNT, ROAD, largest_open_width

ASSIGNMENT = "training__C135702__NRS-484B-450-1k__motor_vehicle_driver"
POSITIONS = {"alongside": (7.5, 2.2), "opposite": (2.5, -2.2)}
KINDS = {"physical_obstruction", "excavation"}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inside(outer: tuple[float, ...], inner: tuple[float, ...]) -> bool:
    return outer[0] < inner[0] < inner[2] < outer[2] and outer[1] < inner[1] < inner[3] < outer[3]


def check_geometry(request: dict) -> dict:
    """Check the authored spatial alternative and preserve readback uncertainty."""
    placement = request.get("placement_request")
    kind = request.get("obstruction_kind_request")
    if placement not in POSITIONS or kind not in KINDS:
        raise ValueError("Unknown statutory placement or obstruction kind")
    center = POSITIONS[placement]
    park_body = (center[0] - 2.4, center[1] - .9, center[0] + 2.4, center[1] + .9)
    if not _inside(ROAD, park_body) or not _inside(ROAD, EXCAVATION):
        raise ValueError("Authored body or obstruction misses surveyed highway")
    same_side = (center[1] > 0) == ((EXCAVATION[1] + EXCAVATION[3]) / 2 > 0)
    if same_side != (placement == "alongside"):
        raise ValueError("Authored alongside/opposite placement differs")
    if placement == "opposite":
        if not (park_body[0] < EXCAVATION[2] and EXCAVATION[0] < park_body[2]):
            raise ValueError("Opposite parked body misses obstruction station")
    elif not (0 < park_body[0] - EXCAVATION[2] <= .5):
        raise ValueError("Alongside parked body overlaps or is remote from obstruction")
    return {"placement_request": placement, "obstruction_kind_request": kind,
            "park_center_xy_m": list(center), "park_body_xy_m": list(park_body),
            "obstruction_xy_m": list(EXCAVATION), "road_xy_m": list(ROAD),
            "authored_open_width_m": largest_open_width(ROAD, [EXCAVATION, park_body]),
            "native_readback_observed": False, "excavation_observed": False,
            "traffic_obstruction_judged": None}


def check_request(config_path: Path, context_path: Path) -> dict:
    """Gate a draft branch against separately hashed reviewed original records."""
    request = json.loads(config_path.read_text())
    case_id = request.get("case_id", "")
    if not case_id.startswith(ASSIGNMENT + "__selected_statutory_"):
        raise ValueError("Exact statutory draft case identity required")
    if (request.get("law_id"), request.get("cell_id"), request.get("actor")) != (
        "NRS-484B-450-1k", "C135702", "motor_vehicle_driver"
    ):
        raise ValueError("Frozen statutory assignment identity differs")
    if (request.get("rate_hz"), request.get("duration_s"), request.get("frames")) != (20, 30, FRAME_COUNT):
        raise ValueError("Exact camera and duration plan differs")
    if request.get("camera_names") != ["overview", "approach", "reference_corner", "driver_reference"]:
        raise ValueError("Four original camera sources required")
    if request.get("physical_acceptance_claimed") is not False or request.get("legal_verdict_claimed") is not False:
        raise ValueError("Draft asserts an unobserved outcome")
    activity, exception = request.get("activity_request"), request.get("exception_request")
    if activity not in ACTIVITIES or exception not in EXCEPTIONS | {None}:
        raise ValueError("Unknown activity or exception request")
    geometry = check_geometry(request)
    gate = validate(context_path.parent, context_path, case_id, activity, exception)
    context = json.loads(context_path.read_text())
    if context.get("activity_request") != activity or context.get("exception_request") != exception:
        raise ValueError("Original branch context request differs")
    spatial = context.get("spatial_source", {})
    if set(spatial) != {"placement", "obstruction_kind"}:
        raise ValueError("Separate placement and obstruction source gates required")
    for name, expected in (("placement", geometry["placement_request"]),
                           ("obstruction_kind", geometry["obstruction_kind_request"])):
        record = checked_record(context_path.parent, spatial[name], name)
        if record.get("requested_value") != expected or not record.get("scene_scope"):
            raise ValueError("Original spatial source differs from request: " + name)
        if name == "obstruction_kind" and expected == "excavation" and not record.get("excavation_source_refs"):
            raise ValueError("Excavation request lacks original excavation source")
    return {"format": "c135702-statutory-draft-gate", "case_id": case_id,
            "config_sha256": _sha(config_path), "context_sha256": _sha(context_path),
            "source_gate_sha256": gate["source_sha256"],
            "spatial_sources": {name: spatial[name]["sha256"] for name in sorted(spatial)},
            "authored_geometry": geometry, "physical_acceptance_claimed": False,
            "legal_acceptance_claimed": False}
