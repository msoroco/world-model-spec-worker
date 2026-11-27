"""Independent saved-source comparison of the two beam request cases."""
from __future__ import annotations

import json
from pathlib import Path

from oncoming_beam import FIVE_HUNDRED_FEET_M
from saved_beam import load_rows, measure_saved, source


FIXED = ("road.xodr", "road-position-source.json", "lighting-trigger-source.json",
         "eye-region-source.json")
POSITION = ("ego_x_m", "ego_y_m", "oncoming_x_m", "oncoming_y_m")
HEADING = ("ego_heading_x", "ego_heading_y", "oncoming_heading_x",
           "oncoming_heading_y")
PAIRS = {
    ("condition_a", "condition_b"): "comparison",
    ("visibility_dim", "visibility_high"): "visibility_1000ft_beam_comparison",
    ("device_dim", "device_high"): "device_directive_beam_comparison",
}


def compare(dim_path, high_path):
    dim_root, high_root = Path(dim_path).resolve(), Path(high_path).resolve()
    dim, high = measure_saved(dim_root), measure_saved(high_root)
    pair = (dim["case_id"].rsplit("__", 1)[-1], high["case_id"].rsplit("__", 1)[-1])
    if pair not in PAIRS or dim["case_id"].rsplit("__", 1)[0] != high["case_id"].rsplit("__", 1)[0]:
        raise ValueError("beam comparison case identity differs")
    if any(dim["source_sha256"][name] != high["source_sha256"][name] for name in FIXED):
        raise ValueError("beam comparison fixed source differs")
    # Actor IDs and absolute CARLA frame numbers are run-local identities.
    # Compare their independently retained role/source semantics instead.
    a_driver = json.loads(source(dim_root, "oncoming-driver-source.json").read_text())
    b_driver = json.loads(source(high_root, "oncoming-driver-source.json").read_text())
    if any(a_driver.get(key) != b_driver.get(key) for key in
           ("oncoming_actor_source", "driver_eye_identity_review_required")):
        raise ValueError("beam comparison oncoming role source differs")
    a = load_rows(source(dim_root, "beam-rows.jsonl"))
    b = load_rows(source(high_root, "beam-rows.jsonl"))
    if len(a) != 600 or len(b) != 600 or any(
            left.get("frame") != right.get("frame") or
            abs(left["time_s"] - right["time_s"]) > .05 or
            any(abs(left[key] - right[key]) > .5 for key in POSITION) or
            any(abs(left[key] - right[key]) > .01 for key in HEADING)
            for left, right in zip(a, b)):
        raise ValueError("beam comparison trajectory differs")
    zone = [i for i, (left, right) in enumerate(zip(a, b))
            if ((left["ego_x_m"]-left["oncoming_x_m"])**2 +
                (left["ego_y_m"]-left["oncoming_y_m"])**2)**.5 <= FIVE_HUNDRED_FEET_M]
    if not zone or any(a[i]["requested_beam_state"] != "low_beam" or
                       b[i]["requested_beam_state"] != "high_beam" for i in zone):
        raise ValueError("beam comparison lacks requested within-500-foot contrast")
    return {"case_ids": [dim["case_id"], high["case_id"]],
            "comparison_id": (dim["case_id"].rsplit("__", 1)[0] + "__comparison"
                              if pair[0] == "condition_a" else
                              dim["case_id"].rsplit("__", 1)[0] + "__" + PAIRS[pair]),
            "fixed_source_count": len(FIXED), "joined_frames": 600,
            "trajectory_tolerance_m": .5,
            "contrasting_within_500_feet_frames": len(zone),
            "physical_glare_conclusion": None, "legal_verdict_claimed": False}
