"""CPU-testable overtaken-vehicle target and feedback controller.

Native code must supply notice and pass-completion facts from retained sources.
The engineering targets here are scenario knobs, never legal thresholds.
"""
from __future__ import annotations

import math


CASES = {
    "gives_way_holds_speed": ("audible_signal", False, 1.0, False),
    "no_right_yield_holds_speed": ("audible_signal", False, 0.0, False),
    "gives_way_increases_speed": ("audible_signal", False, 1.0, True),
    "right_pass_permitted_no_right_yield": ("audible_signal", True, 0.0, False),
    "observed_gives_way_holds_speed": ("observed_vehicle", False, 1.0, False),
}


def target(case_suffix, *, notice_kind, notice_source, pass_complete, baseline_speed_mps=5.0):
    """Return fixed scenario targets after source-backed event readback."""
    if case_suffix not in CASES:
        raise ValueError("Unknown overtaken-driver exact case")
    expected_notice, right_pass, right_shift, early_increase = CASES[case_suffix]
    if notice_kind not in (None, expected_notice):
        raise ValueError("Notice mode differs from exact case")
    if notice_kind is not None and not notice_source:
        raise ValueError("Notice requires a retained source")
    if not isinstance(pass_complete, bool):
        raise ValueError("Pass completion must be original-source boolean readback")
    if not math.isfinite(baseline_speed_mps) or baseline_speed_mps <= 0:
        raise ValueError("Baseline speed must be positive and finite")
    active = notice_kind is not None
    offset = right_shift if active and not right_pass else 0.0
    speed = baseline_speed_mps + (1.0 if (pass_complete or (active and early_increase)) else 0.0)
    return {"target_right_offset_m": offset, "target_speed_mps": speed,
            "notice_kind": notice_kind, "notice_source": notice_source,
            "right_pass_permitted_premise": right_pass,
            "pass_complete_source_readback": pass_complete,
            "phase": "post_pass" if pass_complete else ("response" if active else "approach"),
            "legal_conclusion": None}


def feedback(plan, *, right_offset_m, speed_mps):
    """Produce CARLA-shaped control scalars from original body/velocity feedback."""
    if not all(math.isfinite(v) for v in (right_offset_m, speed_mps)):
        raise ValueError("Original motion feedback must be finite")
    right_error = plan["target_right_offset_m"] - right_offset_m
    speed_error = plan["target_speed_mps"] - speed_mps
    # CARLA positive steer turns left; the measured offset is positive right.
    return {"steer": max(-1.0, min(1.0, -0.7 * right_error)),
            "throttle": max(0.0, min(1.0, 0.3 * speed_error)),
            "brake": max(0.0, min(1.0, -0.4 * speed_error))}


def apply(vehicle, control_factory, plan, *, right_offset_m, speed_mps):
    """Exercise the Native vehicle call through an injected control factory."""
    controls = feedback(plan, right_offset_m=right_offset_m, speed_mps=speed_mps)
    vehicle.apply_control(control_factory(**controls))
    return controls
