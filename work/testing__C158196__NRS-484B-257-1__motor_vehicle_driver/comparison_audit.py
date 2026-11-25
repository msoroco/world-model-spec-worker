"""Source-bound comparison audit for the three C158196 contrasts.

The positional attempts are real saved Native attempts in the case order recorded
in case-plan.json. Diagnostic mode can exercise the joins but cannot accept delivery.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from delivery_audit import PREFIX, audit as delivery_audit


PAIRS = {
    "nearest_view_conflict_response": ("nearest_view_hold", "nearest_view_continue"),
    "nearest_view_traffic_occupancy": ("nearest_view_continue", "nearest_view_clear"),
    "governing_signal_exception": ("nearest_view_clear", "active_signal_exception"),
}
LAYOUT = (
    "cell_id", "law_id", "connected_approach", "intersection_entry_station_m",
    "nearest_view_station_m", "marked_stop_line", "near_side_crosswalk",
    "sidewalk_derived_crosswalk", "through_highway", "proper_yield_sign",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def source(attempt: Path) -> dict:
    return json.loads((attempt / "nearest-view-original.json").read_text(encoding="utf-8"))


def compare(comparison_id: str, first: Path, second: Path, diagnostic: bool = False) -> dict:
    require(comparison_id in PAIRS, "unknown exact comparison")
    variants = PAIRS[comparison_id]
    attempts = (first, second)
    delivery = [delivery_audit(PREFIX + variant, attempt, diagnostic) for variant, attempt in zip(variants, attempts)]
    originals = [source(attempt) for attempt in attempts]
    a, b = originals
    require(all(a["context"].get(key) == b["context"].get(key) for key in LAYOUT), "fixed site or legal layout differs")
    require(all(len(item["frames"]) == 900 and len(item["raw_frames"]) == 900 for item in originals), "source coverage differs")
    require(all(x["frame"] == y["frame"] and x["time_s"] == y["time_s"] for x, y in zip(a["frames"], b["frames"])), "comparison frame/time alignment differs")
    require(all(x["yield_sign_readback"] and not x["officer_controlling"] for item in originals for x in item["raw_frames"]), "fixed yield or officer source differs")
    if comparison_id == "nearest_view_conflict_response":
        require(not a["context"]["signal_controlling"] and not b["context"]["signal_controlling"], "signal must not govern either conflict case")
        require(all(x["through_occupied"] == y["through_occupied"] for x, y in zip(a["frames"], b["frames"])), "traffic occupancy not isolated")
        require(any(x["through_occupied"] for x in a["frames"]), "through conflict not observed")
        difference = min(x["ego_speed_mps"] for x in a["frames"] if x["through_occupied"]) < min(x["ego_speed_mps"] for x in b["frames"] if x["through_occupied"])
        require(difference, "ego conflict response difference not measured")
    elif comparison_id == "nearest_view_traffic_occupancy":
        require(not a["context"]["signal_controlling"] and not b["context"]["signal_controlling"], "signal must not govern either occupancy case")
        require([x["ego_speed_mps"] for x in a["frames"]] == [x["ego_speed_mps"] for x in b["frames"]], "ego continuation policy not fixed")
        require(any(x["through_occupied"] for x in a["frames"]) and not any(x["through_occupied"] for x in b["frames"]), "through occupancy difference not measured")
    else:
        require(not a["context"]["signal_controlling"] and b["context"]["signal_controlling"], "governing signal difference not measured")
        require(all(not x["signal_controlling"] for x in a["raw_frames"]) and any(x["signal_controlling"] for x in b["raw_frames"]), "Native signal readback difference missing")
    require(diagnostic or all(x["delivery_accepted"] for x in delivery), "production delivery not accepted")
    return {"comparison_id": comparison_id, "case_ids": [PREFIX + x for x in variants], "frame_count": 900, "fixed_conditions": "source_verified", "deliberate_difference": "source_measured", "diagnostic": diagnostic, "comparison_accepted": not diagnostic}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("comparison_id", choices=tuple(PAIRS))
    parser.add_argument("first_attempt", type=Path)
    parser.add_argument("second_attempt", type=Path)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(compare(args.comparison_id, args.first_attempt, args.second_attempt, args.diagnostic), sort_keys=True))
