"""Engineering signal requests for the five selected C177008 course changes.

Requests are not observed indicator state or a legal conclusion. The saved
Native light readback and traveled path determine the measured distance.
"""

from __future__ import annotations

from math import isfinite

METRES_PER_FOOT = 0.3048
SAMPLE_PERIOD_S = 0.05
TARGETS_FT = {
    "business_sufficient": 35.0 / METRES_PER_FOOT,
    "business_short": 20.0 / METRES_PER_FOOT,
    "business_interrupted": 35.0 / METRES_PER_FOOT,
    "other_area_short": 35.0 / METRES_PER_FOOT,
    "business_rain": 35.0 / METRES_PER_FOOT,
}


def request_right_signal(case_tag: str, remaining_path_m: float, speed_m_s: float,
                         *, lead_samples: int = 1, course_changed: bool = False) -> bool:
    """Request the right lamp from observed remaining path and speed.

    A one- or two-sample lead allows the first retained active readback to
    precede the authored target. It is an engineering sampling allowance, not
    a change to the statutory distance. A case remains unproved until saved
    original readback and motion establish the actual continuous distance.
    """
    if case_tag not in TARGETS_FT:
        raise ValueError("unknown exact signal case")
    if not isfinite(remaining_path_m) or remaining_path_m < 0:
        raise ValueError("invalid remaining path")
    if not isfinite(speed_m_s) or speed_m_s < 0:
        raise ValueError("invalid observed speed")
    if type(lead_samples) is not int or lead_samples not in (1, 2):
        raise ValueError("unsupported lead samples")
    if course_changed:
        return False
    lead_m = lead_samples * speed_m_s * SAMPLE_PERIOD_S
    return remaining_path_m <= TARGETS_FT[case_tag] * METRES_PER_FOOT + lead_m
