"""Independent saved-source comparisons for the three C158208 yield contrasts.

The diagnostic switch exercises the checker on short synthetic CPU fixtures. It
never turns those fixtures into a physical or legal acceptance claim.
"""

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PREFIX = "testing__C158208__NRS-484B-257-2__motor_vehicle_driver__"
PAIRS = {
    "other_obligation": ("yield_other_inside", "yield_other_obligated"),
    "other_presence": ("yield_other_inside", "yield_other_approaching"),
    "yield_response": ("yield_other_inside", "yield_no_slow"),
}
CAMERAS = ("overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _source_bound(root, report):
    sources = report.get("raw_observations", {}).get("sources", {})
    for name in ("intersection_context.json", "entry_history.jsonl", "video_frames.jsonl",
                 "site_review.json", *CAMERAS):
        if sources.get(name) != sha(root / name):
            raise ValueError("Comparison source hash changed: " + name)
    if report.get("legal_conclusion") != "unresolved":
        raise ValueError("Comparison asserted a legal outcome")


def _fixed_config(left, right):
    for name in ("law_id", "cell_id", "actor", "rate_hz", "duration_s", "cameras",
                 "required_atoms", "source_packets"):
        if left.get(name) != right.get(name):
            raise ValueError("Fixed comparison configuration changed: " + name)
    if (left["law_id"], left["cell_id"], left["actor"], left["rate_hz"], left["duration_s"]) != (
            "NRS-484B-257-2", "C158208", "motor_vehicle_driver", 20, 30):
        raise ValueError("Wrong fixed signed-entrance capture profile")


def audit(attempts, comparison, *, diagnostic_fixture=False):
    if comparison not in PAIRS or len(attempts) != 2:
        raise ValueError("Unknown or incomplete exact comparison")
    roots = [Path(path) for path in attempts]
    expected = [PREFIX + suffix for suffix in PAIRS[comparison]]
    configs = [read(root / "config.json") for root in roots]
    if [config.get("selected_case_id") for config in configs] != expected:
        raise ValueError("Comparison case IDs or order changed")
    _fixed_config(*configs)
    reports = [read(root / "analysis-report.json") for root in roots]
    histories = [rows(root / "entry_history.jsonl") for root in roots]
    frames = [rows(root / "video_frames.jsonl") for root in roots]
    contexts = [read(root / "intersection_context.json") for root in roots]
    for case_id, root, report, history, frame in zip(expected, roots, reports, histories, frames):
        _source_bound(root, report)
        if (report.get("case_id") != case_id
                or len(history) != len(frame) or len(history) < 3):
            raise ValueError("Incomplete original-frame comparison source")
        if not diagnostic_fixture and len(history) != 600:
            raise ValueError("Physical comparison needs the complete 600-frame capture")
        if not diagnostic_fixture:
            sealed = read(root / "result.json")
            review = read(root / "site_review.json")
            if (sealed.get("provenance_kind") != "native"
                    or sealed.get("maneuver_completed") is not True
                    or sealed.get("physical_checks", {}).get("maneuver", {}).get("status") != "met"
                    or not review.get("reviewer")
                    or str(review["reviewer"]).startswith("CPU diagnostic")):
                raise ValueError("Physical comparison lacks Native completion and independent site review")
        if [row.get("frame") for row in history] != [row.get("carla_frame") for row in frame]:
            raise ValueError("Original actor/frame join changed")
    for name in ("native_map_id", "intersection_id", "ego_approach_road_id",
                 "other_approach_road_id", "native_yield_sign_id", "non_through_highway",
                 "ego_entrance_device", "traffic_signal_control"):
        if contexts[0].get(name) != contexts[1].get(name):
            raise ValueError("Fixed signed-entrance context changed: " + name)
    if (contexts[0].get("police_control"), contexts[1].get("police_control")) != (False, False):
        raise ValueError("Officer control changed in non-officer comparison")
    if comparison != "other_obligation" and contexts[0].get("entrances") != contexts[1].get("entrances"):
        raise ValueError("Fixed entrance-device inventory changed")
    if comparison != "other_obligation" and sha(roots[0] / "road.xodr") != sha(roots[1] / "road.xodr"):
        raise ValueError("Fixed signed-intersection map changed")
    for name in CAMERAS:
        if sha(roots[0] / name) != sha(roots[1] / name):
            raise ValueError("Fixed source camera differs: " + name)
    if [row["carla_frame"] for row in frames[0]] != [row["carla_frame"] for row in frames[1]]:
        raise ValueError("Fixed comparison frame range changed")
    for key in ("ego_road_id", "yield_sign_id", "ego_body_vertices_xy_m",
                "ego_body_before_yield_reference"):
        if comparison != "yield_response" or key != "ego_body_before_yield_reference":
            if [row.get(key) for row in histories[0]] != [row.get(key) for row in histories[1]]:
                raise ValueError("Fixed ego source changed: " + key)
    left, right = [report["raw_observations"] for report in reports]
    if comparison == "other_obligation":
        if [row.get("other_body_vertices_xy_m") for row in histories[0]] != [
                row.get("other_body_vertices_xy_m") for row in histories[1]]:
            raise ValueError("Other motion changed in obligation comparison")
        if (left["other_entrance_device"], right["other_entrance_device"]) != ("none", "stop"):
            raise ValueError("Other entrance obligation did not vary")
        observed = {"other_devices": ["none", "stop"]}
    elif comparison == "other_presence":
        if [row.get("ego_speed_mps") for row in histories[0]] != [
                row.get("ego_speed_mps") for row in histories[1]]:
            raise ValueError("Ego response changed in presence comparison")
        if (left["other_inside_at_ego_entry"], right["other_inside_at_ego_entry"]) != (True, False):
            raise ValueError("Other occupancy did not vary")
        if [row.get("other_body_vertices_xy_m") for row in histories[0]] == [
                row.get("other_body_vertices_xy_m") for row in histories[1]]:
            raise ValueError("Other path did not vary")
        observed = {"other_inside_at_ego_entry": [True, False]}
    else:
        if [row.get("other_body_vertices_xy_m") for row in histories[0]] != [
                row.get("other_body_vertices_xy_m") for row in histories[1]]:
            raise ValueError("Other traffic changed in response comparison")
        if (left["observed_slowed_or_stopped_before_reference"],
                right["observed_slowed_or_stopped_before_reference"]) != (True, False):
            raise ValueError("Observed yield response did not vary")
        observed = {"pre_reference_slowing": [True, False]}
    return {"format": "worker-c158208-2-independent-source-comparison",
            "comparison_id": comparison, "case_ids": expected,
            "analysis_sha256": [sha(root / "analysis-report.json") for root in roots],
            "entry_history_sha256": [sha(root / "entry_history.jsonl") for root in roots],
            "observed": observed, "software_comparison_passed": True,
            "physical_acceptance_claimed": False, "legal_conclusion": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--attempt", action="append", required=True)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.comparison,
                           diagnostic_fixture=args.diagnostic_fixture), sort_keys=True))


if __name__ == "__main__":
    main()
