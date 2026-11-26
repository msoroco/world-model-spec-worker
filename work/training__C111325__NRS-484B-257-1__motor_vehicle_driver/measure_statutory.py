"""Saved-source observations for NRS 484B.257(1); no legal classification."""

import hashlib
import math

from stop_yield_scene import CASES

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCE_NAMES = ("map", "sign", "reference", "controls", "through_road", "ego_body", "through_body")


def finite(value, field):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Missing finite saved value: " + field)
    return float(value)


def sha256(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def measure(context, rows, expected_case):
    prefix = "training__C111325__NRS-484B-257-1__motor_vehicle_driver__"
    if not expected_case.startswith(prefix) or expected_case[len(prefix):] not in CASES or context.get("case_id") != expected_case:
        raise ValueError("Exact case source identity differs")
    slug = expected_case[len(prefix):]
    if context.get("source_kind") not in ("original_native_readback", "synthetic_diagnostic"):
        raise ValueError("Original or declared diagnostic source kind required")
    for name in SOURCE_NAMES:
        if not sha256(context.get(name + "_sha256")):
            raise ValueError("Missing source SHA-256: " + name)
    sign = context.get("sign_kind")
    if sign not in ("stop", "yield") or sign != ("yield" if slug.startswith("yield_sign_") else "stop"):
        raise ValueError("Governing sign differs from exact case")
    reference = context.get("reference_kind")
    expected_reference = "crosswalk" if slug == "stop_before_crosswalk_no_line" else (
        "nearest_viewpoint" if slug == "stop_at_viewpoint_no_line_crosswalk" else "stop_line")
    if reference != expected_reference:
        raise ValueError("Stopping-reference hierarchy differs from exact case")
    if context.get("marked_line_present") is not (reference == "stop_line"):
        raise ValueError("Marked stop-line source conflicts with hierarchy")
    if context.get("crosswalk_present") is not (reference == "crosswalk"):
        raise ValueError("Crosswalk source conflicts with hierarchy")
    if reference == "nearest_viewpoint" and not context.get("sight_ray_source"):
        raise ValueError("Nearest viewpoint lacks original sight-ray source")
    police = context.get("police_controlling")
    signal = context.get("signal_controlling")
    if type(police) is not bool or type(signal) is not bool or (police and signal):
        raise ValueError("Ambiguous controlling source")
    if (police, signal) != (slug == "police_directed_control", slug == "signal_directed_control"):
        raise ValueError("Control exception differs from exact case")
    if (police or signal) and not context.get("controlling_direction_source"):
        raise ValueError("Control exception lacks officer/signal direction source")
    reference_x = finite(context.get("reference_x_m"), "reference_x_m")
    near = finite(context.get("intersection_near_x_m"), "intersection_near_x_m")
    far = finite(context.get("intersection_far_x_m"), "intersection_far_x_m")
    through_halfwidth = finite(context.get("through_conflict_halfwidth_m"), "through_conflict_halfwidth_m")
    if not reference_x < near < far or through_halfwidth <= 0:
        raise ValueError("Invalid source reference/intersection geometry")
    if len(rows) != 600:
        raise ValueError("Incomplete saved 600-frame history")
    first_ref = first_enter = last_inside = None
    preceding_rest = []
    through_entered = []
    through_approaching = []
    simultaneous = []
    nearest_gap = None
    prev_native = -1
    prev_front = None
    speeds = []
    for i, row in enumerate(rows):
        native = row.get("native_frame")
        if row.get("video_frame") != i or type(native) is not int or native <= prev_native:
            raise ValueError("Saved Native/video identity join differs")
        prev_native = native
        if abs(finite(row.get("time_s"), "time_s") - i / 20) > .005:
            raise ValueError("Saved 20 Hz time join differs")
        cameras = row.get("source_cameras")
        if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS) or any(cameras[name] != native for name in CAMERAS):
            raise ValueError("Four original source-camera frame identities differ")
        x = finite(row.get("ego_x_m"), "ego_x_m")
        length = finite(row.get("ego_length_m"), "ego_length_m")
        speed = finite(row.get("ego_speed_mps"), "ego_speed_mps")
        other_y = finite(row.get("through_y_m"), "through_y_m")
        other_length = finite(row.get("through_length_m"), "through_length_m")
        other_speed = finite(row.get("through_speed_mps"), "through_speed_mps")
        if length <= 0 or other_length <= 0 or speed < 0 or other_speed < 0:
            raise ValueError("Invalid original body or movement")
        front, rear = x + length / 2, x - length / 2
        if prev_front is not None and front < prev_front - .005:
            raise ValueError("Subject reversed on governed approach")
        prev_front = front
        if first_ref is None and front >= reference_x:
            first_ref = i
        if first_ref is None and front < reference_x and speed <= .1:
            preceding_rest.append(i)
        inside = front >= near and rear <= far
        if inside:
            if first_enter is None:
                first_enter = i
            last_inside = i
            gap = abs(other_y) - other_length / 2 - through_halfwidth
            nearest_gap = gap if nearest_gap is None else min(nearest_gap, gap)
            if gap <= 0:
                through_entered.append(i)
                simultaneous.append(i)
            elif other_y < 0 and other_speed > 0:
                through_approaching.append(i)
        speeds.append(speed)
    if first_ref is None or first_enter is None or last_inside is None or last_inside == 599:
        raise ValueError("Full reference crossing and intersection exit missing")
    return {
        "format": "nrs-484b-257-1-saved-observation-v1", "case_id": expected_case,
        "source_kind": context["source_kind"],
        "source_hashes": {name: context[name + "_sha256"] for name in SOURCE_NAMES},
        "sample_count": 600, "rate_hz": 20, "sign_kind": sign,
        "stopping_reference": reference, "first_reference_crossing_frame": first_ref,
        "rest_frames_before_reference": preceding_rest,
        "minimum_speed_before_reference_mps": min(speeds[:first_ref]) if first_ref else None,
        "initial_observed_speed_mps": speeds[0],
        "intersection_entry_frame": first_enter, "intersection_last_frame": last_inside,
        "through_entered_while_crossing_frames": through_entered,
        "through_approaching_while_crossing_frames": through_approaching,
        "simultaneous_occupancy_frames": simultaneous,
        "minimum_observed_through_gap_m": nearest_gap,
        "controlling_exception": "police" if police else "signal" if signal else None,
        "legal_immediate_hazard": "unassessed", "legal_yield": "unassessed",
        "legal_verdict": None, "physical_acceptance_claimed": False,
        "limitations": ["Saved geometry and motion are measurements; human perception and immediate hazard require independent original-source review.",
                        "0.1 m/s resting threshold is an engineering diagnostic, not a statutory boundary."]}


def diagnostic_hash(name):
    return hashlib.sha256(("synthetic diagnostic only: " + name).encode()).hexdigest()
