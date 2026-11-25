"""Independent source-based comparison checks; no legal verdict or cutoff."""

import argparse
import json
from pathlib import Path

from saved_finalizer import validate_saved


PAIRS = {
    "active_vs_off_signal_exception": ("active_signal_controls", "signal_off_signed_duty"),
    "governing_vs_elsewhere_signal": ("active_signal_controls", "signal_elsewhere_no_control"),
    "yield_vs_stop_signed_duty": ("signal_off_signed_duty", "signal_off_stop_signed_duty"),
    "approaching_traffic_separation": ("approaching_traffic_close", "approaching_traffic_far"),
}


def _assert_equal(left, right, label):
    if left != right:
        raise ValueError("Fixed comparison condition changed: " + label)


def audit(comparison_id, first, second):
    if comparison_id not in PAIRS:
        raise ValueError("Unknown subsection 2 comparison")
    left, right = validate_saved(first), validate_saved(second)
    a, b = left[0], right[0]
    suffixes = PAIRS[comparison_id]
    if not a["selected_case_id"].endswith("__" + suffixes[0]) or not b["selected_case_id"].endswith("__" + suffixes[1]):
        raise ValueError("Comparison has wrong exact case order")
    for key in ("law_id", "cell_id", "actor", "rate_hz", "duration_s", "cameras", "camera_mounts", "actor_blueprints"):
        _assert_equal(a.get(key), b.get(key), key)
    ma, mb = a["motion"], b["motion"]
    for key in ("ego_start_xy_m", "ego_hold_ticks", "ego_throttle", "other_throttle", "rate_hz", "duration_s"):
        _assert_equal(ma.get(key), mb.get(key), key)
    ia = json.loads((Path(first) / "entrance_inventory.json").read_text())
    ib = json.loads((Path(second) / "entrance_inventory.json").read_text())
    for key in ("intersection_polygon_xy_m", "ego_lane_key", "other_lane_key", "non_through_highway"):
        _assert_equal(ia.get(key), ib.get(key), key)
    ra, rb = left[1], right[1]
    if ra["other_entrance_device"] != "none" or rb["other_entrance_device"] != "none":
        raise ValueError("Other party is not shown as non-obligated")
    if comparison_id != "approaching_traffic_separation":
        _assert_equal(ma.get("other_start_xy_m"), mb.get("other_start_xy_m"), "other start")
        _assert_equal(ma.get("other_hold_ticks"), mb.get("other_hold_ticks"), "other hold")
    if comparison_id == "active_vs_off_signal_exception":
        _assert_equal(ma.get("site_sha256"), mb.get("site_sha256"), "authored site")
        _assert_equal(ra["ego_entrance_device"], rb["ego_entrance_device"], "ego sign")
        if not (ma["signal_state"] == "Green" and mb["signal_state"] == "Off" and
                ra["operative_signal_controls_ego_at_entry_observed"] and
                not rb["operative_signal_controls_ego_at_entry_observed"]):
            raise ValueError("Governing active/Off contrast not observed")
    elif comparison_id == "governing_vs_elsewhere_signal":
        _assert_equal(ma.get("signal_state"), mb.get("signal_state"), "signal state")
        _assert_equal(ra["ego_entrance_device"], rb["ego_entrance_device"], "ego sign")
        if not (ia.get("authored_signal_governs_ego") is True and
                ib.get("authored_signal_governs_ego") is False and
                ra["operative_signal_controls_ego_at_entry_observed"] and
                not rb["operative_signal_controls_ego_at_entry_observed"]):
            raise ValueError("Governing versus elsewhere contrast not observed")
    elif comparison_id == "yield_vs_stop_signed_duty":
        _assert_equal(ma.get("signal_state"), mb.get("signal_state"), "signal state")
        if not (ra["ego_entrance_device"] == "yield" and rb["ego_entrance_device"] == "stop" and
                not ra["operative_signal_controls_ego_at_entry_observed"] and
                not rb["operative_signal_controls_ego_at_entry_observed"]):
            raise ValueError("Yield versus stop signed-entrance contrast not observed")
    elif comparison_id == "approaching_traffic_separation":
        _assert_equal(ma.get("site_sha256"), mb.get("site_sha256"), "authored site")
        _assert_equal(ma.get("signal_state"), mb.get("signal_state"), "signal state")
        _assert_equal(ra["ego_entrance_device"], rb["ego_entrance_device"], "ego sign")
        near = ra["samples"][0]["other_time_to_conflict_s"]
        far = rb["samples"][0]["other_time_to_conflict_s"]
        if near is None or far is None or not near < far:
            raise ValueError("Original approaching separation is not ordered")
    return {"format": "worker-subsection-2-comparison-audit", "comparison_id": comparison_id,
            "case_ids": [a["selected_case_id"], b["selected_case_id"]],
            "source_sha256": {"first": left[4], "second": right[4]},
            "observed": {"first_signal_control": ra["operative_signal_controls_ego_at_entry_observed"],
                         "second_signal_control": rb["operative_signal_controls_ego_at_entry_observed"],
                         "first_device": ra["ego_entrance_device"],
                         "second_device": rb["ego_entrance_device"]},
            "fixed_conditions_checked": True, "deliberate_difference_observed": True,
            "physical_acceptance_claimed": False, "legal_conclusion": "unresolved"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--first", required=True)
    parser.add_argument("--second", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = audit(args.comparison, Path(args.first), Path(args.second))
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
