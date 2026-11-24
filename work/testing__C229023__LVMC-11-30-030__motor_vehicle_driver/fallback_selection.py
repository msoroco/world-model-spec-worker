"""Select a slower new attempt from sealed original crossing timing.

This evaluates an engineering retry trigger, never a legal conclusion or a
claim that the fallback physically succeeds.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from crosswalk_measurements import measure


def evaluate(*, case_id: str, context_path: str | Path,
             trace_path: str | Path, receipt_path: str | Path) -> dict:
    measured = measure(case_id=case_id, context_path=context_path,
                       trace_path=trace_path, receipt_path=receipt_path)
    context = json.loads(Path(context_path).read_text())
    road = context["road_axis"]
    ox, oy = road["origin"]
    ax, ay = road["forward"]
    polygon = context["crosswalk"]["polygon"]
    if not isinstance(polygon, list) or len(polygon) < 3:
        raise ValueError("original crossing polygon required")
    stations = [(point[0] - ox) * ax + (point[1] - oy) * ay for point in polygon]
    if not all(math.isfinite(value) for value in stations):
        raise ValueError("finite original crossing entry required")
    entry_station = min(stations)
    rows = measured["observations"]
    if len(rows) != 900 or rows[0]["ego_front_station_m"] >= entry_station:
        raise ValueError("complete original ego crossing approach required")
    entering = next((row for row in rows if row["ego_front_station_m"] >= entry_station), None)
    pedestrian_frames = measured["pedestrian_crosswalk_frames"]
    if entering is None or not pedestrian_frames:
        outcome = "insufficient_ego_entry_or_pedestrian_crossing"
        retry = False
    else:
        last_pedestrian_frame = pedestrian_frames[-1]
        retry = entering["frame"] <= last_pedestrian_frame
        outcome = "timing_overlap" if retry else "timing_clear"
    return {
        "case_id": case_id, "candidate_id": "fallback1" if retry else "primary",
        "retry_trigger_met": retry, "outcome": outcome,
        "ego_crossing_entry_frame": entering["frame"] if entering else None,
        "pedestrian_clearance_last_frame": pedestrian_frames[-1] if pedestrian_frames else None,
        "entry_minus_clearance_s": ((entering["frame"] - pedestrian_frames[-1]) / 20.0
                                    if entering is not None and pedestrian_frames else None),
        "crossing_entry_station_m": entry_station,
        "source_bindings": measured["source_bindings"],
        "physical_acceptance": "unverified", "legal_judgment": "unresolved",
    }
