"""Independent saved-source comparisons for the three C158208 yield contrasts.

The diagnostic switch exercises the checker on short synthetic CPU fixtures. It
never turns those fixtures into a physical or legal acceptance claim.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon


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


def _center(vertices):
    if not isinstance(vertices, list) or len(vertices) < 4:
        raise ValueError("Incomplete original vehicle body")
    points = [(float(point[0]), float(point[1])) for point in vertices]
    if any(not math.isfinite(value) for point in points for value in point):
        raise ValueError("Nonfinite original vehicle body")
    return tuple(sum(point[axis] for point in points) / len(points) for axis in (0, 1))


def _observed(history, context, report):
    polygon = Polygon(context.get("intersection_polygon_xy_m", []))
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("Invalid original intersection geometry")
    entrances = [item for item in context.get("entrances", [])
                 if item.get("road_id") == context.get("other_approach_road_id")]
    if len(entrances) != 1 or entrances[0].get("device") not in ("none", "yield", "stop"):
        raise ValueError("Other entrance inventory unresolved")
    entry = next((row for row in history
                  if MultiPoint(row["ego_body_vertices_xy_m"]).convex_hull.intersects(polygon)), None)
    if entry is None:
        raise ValueError("No source-observed ego entry")
    prior = [row for row in history if row["time_s"] < entry["time_s"]
             and row["ego_body_before_yield_reference"] is True]
    speeds = [float(row["ego_speed_mps"]) for row in prior]
    if any(not math.isfinite(speed) or speed < 0 for speed in speeds):
        raise ValueError("Invalid original ego speed")
    observed = {
        "first_ego_entry": {"frame": entry["frame"], "time_s": entry["time_s"]},
        "other_entrance_device": entrances[0]["device"],
        "other_inside_at_ego_entry": MultiPoint(entry["other_body_vertices_xy_m"]).convex_hull.intersects(polygon),
        "observed_slowed_or_stopped_before_reference": len(speeds) >= 2 and min(speeds) < speeds[0],
    }
    for key, value in observed.items():
        if report.get(key) != value:
            raise ValueError("Comparison report differs from original source: " + key)
    return observed


def _timeline(history, frames, rate):
    for index, (row, frame) in enumerate(zip(history, frames)):
        if frame.get("video_frame") != index or frame.get("carla_frame") != row.get("frame"):
            raise ValueError("Original actor/frame join changed")
        if index:
            if row["frame"] != history[index - 1]["frame"] + 1:
                raise ValueError("Original frame interval changed")
            if not math.isclose(row["time_s"] - history[index - 1]["time_s"], 1 / rate,
                                abs_tol=0.002):
                raise ValueError("Original capture rate changed")
        if not math.isclose(frame.get("time_s", -1), row["time_s"], abs_tol=1e-6):
            raise ValueError("Original frame time join changed")


def _initial_fixed_actor(left, right, key, tolerance_m=2.0):
    a, b = (_center(row[0][key]) for row in (left, right))
    if math.dist(a, b) > tolerance_m:
        raise ValueError("Fixed initial actor position changed: " + key)


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
    observations = []
    for case_id, root, report, history, frame, context in zip(
            expected, roots, reports, histories, frames, contexts):
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
        _timeline(history, frame, configs[0]["rate_hz"])
        review = read(root / "site_review.json")
        if (review.get("intersection_context_sha256") != sha(root / "intersection_context.json")
                or review.get("camera_sha256") != {name.removesuffix(".mkv"): sha(root / name)
                                                      for name in CAMERAS}
                or review.get("reviewed_carla_frames") != [item["carla_frame"] for item in frame]
                or review.get("reviewed_frame_count") != len(frame)):
            raise ValueError("Original site review source binding changed")
        observations.append(_observed(history, context, report["raw_observations"]))
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
    for history, context in zip(histories, contexts):
        if any(row.get("ego_road_id") != context["ego_approach_road_id"]
               or row.get("yield_sign_id") != context["native_yield_sign_id"] for row in history):
            raise ValueError("Fixed ego road/sign source changed")
    _initial_fixed_actor(*histories, "ego_body_vertices_xy_m")
    left, right = observations
    if comparison == "other_obligation":
        _initial_fixed_actor(*histories, "other_body_vertices_xy_m")
        if (left["other_entrance_device"], right["other_entrance_device"]) != ("none", "stop"):
            raise ValueError("Other entrance obligation did not vary")
        observed = {"other_devices": ["none", "stop"]}
    elif comparison == "other_presence":
        if (left["other_inside_at_ego_entry"], right["other_inside_at_ego_entry"]) != (True, False):
            raise ValueError("Other occupancy did not vary")
        observed = {"other_inside_at_ego_entry": [True, False]}
    else:
        _initial_fixed_actor(*histories, "other_body_vertices_xy_m")
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
