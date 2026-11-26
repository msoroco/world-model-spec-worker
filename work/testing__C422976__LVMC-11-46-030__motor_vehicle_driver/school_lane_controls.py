"""Source-gated engineering controls for the selected school-lane variants.

Targets specify an attempted vehicle station. Original body reference and
nearest-side geometry decide the measured distance after capture.
"""

from dataclasses import dataclass
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C422976__LVMC-11-46-030__motor_vehicle_driver"
FEET_TO_METERS = 0.3048


@dataclass(frozen=True)
class Variant:
    suffix: str
    stop_target_ft: int | None
    warning: str
    release: str
    response: str


VARIANTS = (
    Variant("human_warning_stop_51ft_go", 51, "human", "go", "proceed"),
    Variant("human_warning_stop_50ft_go", 50, "human", "go", "proceed"),
    Variant("human_warning_stop_49ft_go", 49, "human", "go", "proceed"),
    Variant("human_warning_stop_51ft_wait", 51, "human", "continued", "wait"),
    Variant("human_warning_stop_51ft_depart", 51, "human", "depart", "proceed"),
    Variant("human_warning_proceed_before_go", 51, "human", "continued", "premature"),
    Variant("device_warning_stop_51ft_raised", 51, "device", "raised", "proceed"),
    Variant("no_warning_travel", None, "none", "none", "travel"),
    Variant("human_present_no_child_warning", 51, "human_present", "continued", "wait"),
)


def exact_variant(case_id: str) -> Variant:
    for variant in VARIANTS:
        if case_id == ASSIGNMENT + "__" + variant.suffix:
            return variant
    raise ValueError("unselected exact school-lane case")


def station_target_m(nearest_side_m: float, variant: Variant) -> float | None:
    if not isinstance(nearest_side_m, (int, float)) or not math.isfinite(nearest_side_m):
        raise ValueError("reviewed nearest-side station required")
    if variant.stop_target_ft is None:
        return None
    return float(nearest_side_m) - variant.stop_target_ft * FEET_TO_METERS


def control_schedule(variant: Variant, nearest_side_m: float) -> dict:
    """Explicit controls; events are requests pending Native actor readback."""
    stop = station_target_m(nearest_side_m, variant)
    warning_on = variant.warning in {"human", "device"}
    return {
        "case_id": ASSIGNMENT + "__" + variant.suffix,
        "ego_stop_reference_station_target_m": stop,
        "ego_initial_station_m": float(nearest_side_m) - 45.0,
        "ego_initial_speed_mps": 6.0,
        "warning_on_from_frame": 0 if warning_on else None,
        "children_crossing_from_frame": 100 if warning_on else None,
        "stop_hold_start_frame": 300 if stop is not None else None,
        "release_frame": 500 if variant.release in {"go", "depart", "raised"} else None,
        "requested_release": variant.release,
        "requested_warning_actor": variant.warning,
        "requested_ego_response": variant.response,
        "premature_proceed_frame": 400 if variant.response == "premature" else None,
        "capture_frames": 900,
        "capture_hz": 20,
        "legal_judgment": "unresolved",
    }


def selected_schedule(case_id: str, nearest_side_m: float) -> dict:
    """Resolve only a selected exact case and its frozen physical station."""
    if "__child_warning_onset-" not in case_id and "__person_departure_onset-" not in case_id:
        return control_schedule(exact_variant(case_id), nearest_side_m)
    proposal = json.loads((Path(__file__).resolve().parent / "proposals/cases.json").read_text())
    matches = [case for case in proposal["cases"] if case["case_id"] == case_id]
    if len(matches) != 1 or matches[0].get("target_type") != "judgment_sweep":
        raise ValueError("unselected judgment sampling case")
    case = matches[0]
    point = case["sweep_point"]
    if set(point) == {"warning_onset_s"}:
        variant = VARIANTS[0]
        frame = round(point["warning_onset_s"] * 20)
        key = "warning_on_from_frame"
    elif set(point) == {"departure_onset_s"}:
        variant = VARIANTS[4]
        frame = round(point["departure_onset_s"] * 20)
        key = "release_frame"
    else:
        raise ValueError("unsupported judgment sampling point")
    if frame < 0 or frame >= 900:
        raise ValueError("sampling station outside authored episode")
    schedule = control_schedule(variant, nearest_side_m)
    schedule["case_id"] = case_id
    schedule[key] = frame
    if key == "release_frame":
        schedule["stop_hold_start_frame"] = 120
    schedule["sweep_point"] = point
    return schedule


def apply_schedule(adapter, source: dict, case_id: str) -> dict:
    """Call the Native adapter with geometry and separate actor controls."""
    if source.get("source_kind") != "reviewed_original_site":
        raise ValueError("reviewed original site required")
    for key in ("opendrive_sha256", "nearest_side_geometry_sha256",
                "municipal_jurisdiction_source", "ego_approach_lane_id",
                "school_lane_polygon_xy", "human_actor_source", "device_actor_source",
                "child_actor_source", "vehicle_reference_point_source"):
        if not source.get(key):
            raise ValueError("reviewed school-lane source missing: " + key)
    schedule = selected_schedule(case_id, source["nearest_side_station_m"])
    variant = exact_variant(case_id) if "sweep_point" not in schedule else (
        VARIANTS[0] if "warning_onset_s" in schedule["sweep_point"] else VARIANTS[4])
    adapter.load_reviewed_map(source)
    adapter.spawn_vehicle_in_lane(source["ego_approach_lane_id"], schedule)
    adapter.spawn_children(source["child_actor_source"], source["school_lane_polygon_xy"])
    adapter.spawn_warning_actor(variant.warning, source)
    adapter.attach_four_cameras(source)
    adapter.install_schedule(schedule)
    return schedule
