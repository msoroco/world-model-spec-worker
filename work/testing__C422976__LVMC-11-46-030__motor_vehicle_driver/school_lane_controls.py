"""Source-gated engineering controls for the selected school-lane variants.

Targets specify an attempted vehicle station. Original body reference and
nearest-side geometry decide the measured distance after capture.
"""

from dataclasses import dataclass
import math


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
    variant = exact_variant(case_id)
    schedule = control_schedule(variant, source["nearest_side_station_m"])
    adapter.load_reviewed_map(source)
    adapter.spawn_vehicle_in_lane(source["ego_approach_lane_id"], schedule)
    adapter.spawn_children(source["child_actor_source"], source["school_lane_polygon_xy"])
    adapter.spawn_warning_actor(variant.warning, source)
    adapter.attach_four_cameras(source)
    adapter.install_schedule(schedule)
    return schedule
