"""Independent saved-source comparison of the two beam request cases."""
from __future__ import annotations

from pathlib import Path

from oncoming_beam import FIVE_HUNDRED_FEET_M
from saved_beam import load_rows, measure_saved, source


FIXED = ("road.xodr", "road-position-source.json", "lighting-trigger-source.json",
         "oncoming-driver-source.json", "eye-region-source.json")
POSE = ("frame", "native_frame", "time_s", "ego_x_m", "ego_y_m",
        "ego_heading_x", "ego_heading_y", "oncoming_x_m", "oncoming_y_m",
        "oncoming_heading_x", "oncoming_heading_y")


def compare(dim_path, high_path):
    dim_root, high_root = Path(dim_path).resolve(), Path(high_path).resolve()
    dim, high = measure_saved(dim_root), measure_saved(high_root)
    if not dim["case_id"].endswith("__condition_a") or not high["case_id"].endswith("__condition_b"):
        raise ValueError("beam comparison case identity differs")
    if any(dim["source_sha256"][name] != high["source_sha256"][name] for name in FIXED):
        raise ValueError("beam comparison fixed source differs")
    a = load_rows(source(dim_root, "beam-rows.jsonl"))
    b = load_rows(source(high_root, "beam-rows.jsonl"))
    if len(a) != 600 or len(b) != 600 or any(
            any(left.get(key) != right.get(key) for key in POSE)
            for left, right in zip(a, b)):
        raise ValueError("beam comparison trajectory differs")
    zone = [i for i, (left, right) in enumerate(zip(a, b))
            if ((left["ego_x_m"]-left["oncoming_x_m"])**2 +
                (left["ego_y_m"]-left["oncoming_y_m"])**2)**.5 <= FIVE_HUNDRED_FEET_M]
    if not zone or any(a[i]["requested_beam_state"] != "low_beam" or
                       b[i]["requested_beam_state"] != "high_beam" for i in zone):
        raise ValueError("beam comparison lacks requested within-500-foot contrast")
    return {"case_ids": [dim["case_id"], high["case_id"]],
            "fixed_source_count": len(FIXED), "joined_frames": 600,
            "contrasting_within_500_feet_frames": len(zone),
            "physical_glare_conclusion": None, "legal_verdict_claimed": False}
