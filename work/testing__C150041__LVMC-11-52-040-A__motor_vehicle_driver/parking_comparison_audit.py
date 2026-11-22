"""Independent measured-geometry audit for four C150041 comparison pairs.

Engineering separation checks identify useful original observations. They make
no legal conclusion about the meaning of parallel, standing or parking.
"""
from __future__ import annotations

import math

from parking_scene import ASSIGNMENT


PAIRS = {
    "park_parallelism": ("park_parallel_lawful", "park_angled_lawful", "orientation"),
    "park_heading": ("park_parallel_lawful", "park_parallel_reverse", "heading"),
    "stand_parallelism": ("stand_parallel_lawful", "stand_angled_lawful", "orientation"),
    "stand_heading": ("stand_parallel_lawful", "stand_parallel_reverse", "heading"),
}


def _last_stationary(result):
    intervals = result.get("stationary_intervals")
    if not intervals:
        raise ValueError("comparison lacks original stationary interval")
    last = intervals[-1]["last_frame"]
    matches = [item for item in result["observations"] if item["frame"] == last]
    if len(matches) != 1 or not matches[0]["engineering_stationary"]:
        raise ValueError("comparison stationary frame cannot be joined")
    return matches[0]


def audit(left, right, comparison_id):
    if comparison_id not in PAIRS:
        raise ValueError("unknown exact parking comparison")
    first, second, variable = PAIRS[comparison_id]
    if (left.get("case_id"), right.get("case_id")) != (ASSIGNMENT + "__" + first,
                                                    ASSIGNMENT + "__" + second):
        raise ValueError("comparison case identities or order differ")
    if left.get("source_packet_sha256") != right.get("source_packet_sha256"):
        raise ValueError("comparison source packet differs")
    if left.get("original_history_sha256") == right.get("original_history_sha256"):
        raise ValueError("comparison original histories are identical")
    if left.get("legal_judgment") != "unresolved" or right.get("legal_judgment") != "unresolved":
        raise ValueError("comparison must preserve legal uncertainty")
    a, b = _last_stationary(left), _last_stationary(right)
    if a["body_corners_inside_roadway"] != 4 or b["body_corners_inside_roadway"] != 4:
        raise ValueError("comparison vehicle body leaves reviewed roadway")
    center_gap = math.dist(a["body_center_xy_m"], b["body_center_xy_m"])
    edge_gap = abs(a["center_edge_distance_m"] - b["center_edge_distance_m"])
    if center_gap > 0.35 or edge_gap > 0.35:
        raise ValueError("comparison fixed body placement differs")
    if variable == "orientation":
        if abs(a["lawful_heading_deviation_deg"] - b["lawful_heading_deviation_deg"]) < 10:
            raise ValueError("comparison lacks measured orientation difference")
        separation = abs(a["parallel_deviation_deg"] - b["parallel_deviation_deg"])
        if separation < 10:
            raise ValueError("comparison lacks measured parallelism difference")
    else:
        if abs(a["parallel_deviation_deg"] - b["parallel_deviation_deg"]) > 3:
            raise ValueError("comparison fixed parallel geometry differs")
        separation = abs(a["lawful_heading_deviation_deg"] -
                         b["lawful_heading_deviation_deg"])
        if separation < 90:
            raise ValueError("comparison lacks measured heading difference")
    return {"comparison_id": comparison_id, "case_ids": [left["case_id"], right["case_id"]],
            "source_packet_sha256": left["source_packet_sha256"],
            "original_history_sha256": [left["original_history_sha256"],
                                        right["original_history_sha256"]],
            "controlled_variable": variable,
            "measured_separation_deg": separation,
            "measured_center_gap_m": center_gap,
            "measured_edge_distance_gap_m": edge_gap,
            "engineering_comparison_only": True,
            "legal_judgment": "unresolved",
            "physical_acceptance_claimed": False}
