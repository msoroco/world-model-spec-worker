"""Requested right-signal policy tied to remaining route distance.

The policy requests actuation; only signal_measure.py can report what occurred.
"""

from __future__ import annotations

import math

METRES_PER_FOOT = 0.3048
TARGET_FEET = {"short80": 80.0, "continuous100": 100.0,
               "above101": 101.0, "interrupted": 100.0, "rain": 100.0}


def request_right_signal(case_tag: str, remaining_m: float, course_changed: bool = False,
                         *, speed_m_s: float = 0.0, sample_period_s: float = 0.05) -> bool:
    if case_tag not in TARGET_FEET:
        raise ValueError("unknown exact signal case")
    if not math.isfinite(remaining_m) or remaining_m < 0:
        raise ValueError("invalid remaining route distance")
    if (not math.isfinite(speed_m_s) or speed_m_s < 0 or
            not math.isfinite(sample_period_s) or sample_period_s <= 0 or
            sample_period_s > .05):
        raise ValueError("invalid measured speed or 20 Hz sample period")
    if course_changed:
        return False
    remaining_ft = remaining_m / METRES_PER_FOOT
    # Request up to one measured sampling step before the authored target so
    # the first saved active sample can still lie at or beyond the threshold.
    # The saved measurement, not this request, determines observed coverage.
    active = remaining_ft <= TARGET_FEET[case_tag] + speed_m_s * sample_period_s / METRES_PER_FOOT
    if case_tag == "interrupted" and 55.0 < remaining_ft < 65.0:
        active = False
    return active
