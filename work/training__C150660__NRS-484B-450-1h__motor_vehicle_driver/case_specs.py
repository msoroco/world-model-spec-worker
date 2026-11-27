"""Engineering requests for the fixed one-way safety-zone cell.

Offsets are requested from the nearest vehicle footprint edge to a curb point;
the saved analyzer measures realized distances independently.
"""

from math import sqrt

CASES = {
    "selected_6214a61f__condition_a": ("between", "stop", "none", None),
    "selected_6214a61f__condition_b": ("past_end", "stop", "none", 45.0),
    "end_25": ("past_end", "stop", "none", 25.0),
    "end_30": ("past_end", "stop", "none", 30.0),
    "end_35": ("past_end", "stop", "none", 35.0),
    "start_25": ("before_start", "stop", "none", 25.0),
    "start_30": ("before_start", "stop", "none", 30.0),
    "start_35": ("before_start", "stop", "none", 35.0),
    "stand_between": ("between", "stand", "none", None),
    "park_between": ("between", "park", "none", None),
    "conflict_between": ("between", "stop", "traffic_conflict", None),
    "law_between": ("between", "stop", "other_law", None),
    "officer_between": ("between", "stop", "officer_direction", None),
    "device_between": ("between", "stop", "device_direction", None),
}

def target_x(suffix, vehicle_half_length_m=2.25, curb_clearance_m=.1):
    position, _, _, gap_ft = CASES[suffix]
    if position == "between":
        return 90.0
    gap_m = gap_ft * .3048
    if not 0 <= curb_clearance_m < gap_m:
        raise ValueError("Curb clearance exceeds requested endpoint distance")
    along_curb_m = sqrt(gap_m * gap_m - curb_clearance_m * curb_clearance_m)
    if position == "past_end":
        return 100.0 + along_curb_m + vehicle_half_length_m
    return 80.0 - along_curb_m - vehicle_half_length_m
