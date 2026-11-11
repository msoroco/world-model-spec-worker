"""Saved-only marked-lane measurements from retained original Native sources."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from lane_measurement import measure_saved_sources


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError("Missing required source: " + name)
    return path, sha256(path.read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure_saved_lane(path, ego_id, *, require_overtaken=False):
    return measure_saved_sources(path, expected_ego_id=ego_id,
                                 require_overtaken=require_overtaken)


def observed_lateral_fraction(row):
    """Dimensionless original ego-center excursion from its recorded lane center."""
    lane = row['lane']
    polygon = lane['polygon_xy_m']
    corners = row['ego_corners_xy_m']
    width = lane['lane_width_m']
    if width <= 0 or len(polygon) < 4 or len(corners) < 4:
        raise ValueError('Original lateral-fraction geometry incomplete')
    center = [sum(point[i] for point in polygon) / len(polygon) for i in (0, 1)]
    ego = [sum(point[i] for point in corners) / len(corners) for i in (0, 1)]
    heading = lane['lane_heading_xy']
    normal = (-heading[1], heading[0])
    return abs(sum((ego[i] - center[i]) * normal[i] for i in (0, 1))) / width


def analyze(attempt, *, write_channel=True):
    root = Path(attempt)
    config_path, _ = required(root, "config.json")
    config = json.loads(config_path.read_text())
    case_id = config.get("selected_case_id", "")
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "LVMC-11-18-030-B", "C147331", "motor_vehicle_driver") or not case_id:
        raise ValueError("Wrong exact marked-lane identity")
    map_path, map_sha = required(root, "video_frames.jsonl")
    trace_path, trace_sha = required(root, "trace.jsonl")
    source_path, source_sha = required(root, "marked_lane_sources.jsonl")
    mapping, trace, source_rows = _rows(map_path), _rows(trace_path), _rows(source_path)
    if not mapping or len(mapping) != len(trace) or len(mapping) != len(source_rows):
        raise ValueError("Original lane source/frame-map length differs")
    for index, (frame, motion, lane) in enumerate(zip(mapping, trace, source_rows)):
        identity = (frame.get("carla_frame"), frame.get("time_s"))
        if (frame.get("video_frame") != index or motion.get("frame") != identity[0]
                or motion.get("time_s") != identity[1]
                or lane.get("frame") != identity[0] or lane.get("time_s") != identity[1]):
            raise ValueError("Original lane source/frame-map join failed")
    expected_ego = source_rows[0]["ego_id"]
    measured = measure_saved_lane(source_path, expected_ego,
                                  require_overtaken=(case_id.endswith("__passing_boundary_crossing")
                                                     or "__passing_excursion-" in case_id))
    channel_rows = {
        "lane_clearance_m": [(frame["time_s"], frame["minimum_corner_clearance_m"])
                             for frame in measured["frames"]],
        "native_lane_boundaries": [(row["time_s"], row["lane"]) for row in source_rows],
        "ego_vehicle_footprint": [(row["time_s"], {
            "ego_id": row["ego_id"], "corners_xy_m": row["ego_corners_xy_m"],
            "velocity_xy_mps": row["ego_velocity_xy_mps"]}) for row in source_rows],
        "lane_boundary_overlap": [(frame["time_s"], frame["minimum_corner_clearance_m"])
                                  for frame in measured["frames"]],
        "passing_context": [(row["time_s"], {
            "overtaken_id": row.get("overtaken_id"),
            "corners_xy_m": row.get("overtaken_corners_xy_m"),
            "velocity_xy_mps": row.get("overtaken_velocity_xy_mps")}) for row in source_rows],
        "turn_indicator_state": [(row["time_s"], {
            "ego_light_state": row.get("ego_light_state")}) for row in source_rows],
        "ego_turn_motion": [(row["time_s"], {
            "position": row.get("position"), "heading_deg": row.get("heading_deg"),
            "speed_mps": row.get("speed_mps")}) for row in trace],
    }
    if '__passing_excursion-' in case_id:
        channel_rows['lane_crossing_fraction'] = [
            (row['time_s'], observed_lateral_fraction(row)) for row in source_rows]
    if write_channel:
        for name, values in channel_rows.items():
            channel = root / (name + ".jsonl")
            if channel.exists():
                raise ValueError("Retain prior derived lane channel: " + name)
            channel.write_text("".join(json.dumps({"frame": source_rows[index]["frame"],
                                                    "time_s": time_s, "value": value},
                                                   allow_nan=False) + "\n"
                                       for index, (time_s, value) in enumerate(values)))
    sources = {"video_frames.jsonl": map_sha, "trace.jsonl": trace_sha,
               "marked_lane_sources.jsonl": source_sha}
    return {"format": "worker-analysis-report", "case_id": case_id,
            "measurements": {"lane_boundary_observation": {
                "method": "measure_saved_lane", "value": measured, "sources": sources}},
            "limitations": ["Local waypoint lane slices and synthetic CPU fixture cannot establish physical marking visibility or legal exceptions."],
            "legal_acceptance_claimed": False, "physical_acceptance_claimed": False}


def build_result(attempt, report):
    root = Path(attempt)
    config = json.loads((root / "config.json").read_text())
    description = config.get("case", {}).get("recording_description")
    if not isinstance(description, dict):
        raise ValueError("Selected recording description missing")
    value = report["measurements"]["lane_boundary_observation"]["value"]
    frames = value["frames"]
    minimum = min(frame["minimum_corner_clearance_m"] for frame in frames)
    evidence = []
    for channel_description in description["channels"]:
        name = channel_description["name"]
        path = root / (name + ".jsonl")
        if not path.is_file():
            raise ValueError("Missing derived observation channel: " + name)
        evidence.append({"name": name, "unit": channel_description["unit"],
                         "reference": path.name,
                         "sha256": sha256(path.read_bytes()).hexdigest()})
    realized = {"lane_clearance_m": {
                "unit": "m", "method": "signed minimum ground-corner clearance from original Native lane source",
                "time_window": "all original frames", "statistic": "min",
                "reference": "lane_clearance_m.jsonl", "value": minimum,
                "sample_window_s": [frames[0]["time_s"], frames[-1]["time_s"]]}}
    if '__passing_excursion-' in report['case_id']:
        fraction_rows = _rows(root / 'lane_crossing_fraction.jsonl')
        realized['lane_crossing_fraction'] = {
            'unit': 'fraction',
            'method': 'maximum absolute original ego-center displacement from retained primary lane center, projected across lane heading and divided by retained original lane width',
            'time_window': 'all original frames', 'statistic': 'max',
            'reference': 'lane_crossing_fraction.jsonl',
            'value': max(row['value'] for row in fraction_rows),
            'sample_window_s': [fraction_rows[0]['time_s'], fraction_rows[-1]['time_s']]}
    return {"case_id": report["case_id"],
            "measured_values": {"lane_boundary_observation": value},
            "target_checks": [{"target": "measured marked-lane footprint history",
                               "requested": "retained signed boundary clearances",
                               "measured": minimum, "method": "original Native body corners and waypoint lane slice",
                               "tolerance": None, "matched": False,
                               "physical_cause_confirmed": False,
                               "cause_evidence": "Original lane source joined to frame map; physical marking review pending"}],
            "setup_confirmed": False, "behavior_attempted": True,
            "maneuver_completed": False,
            "termination_reason": "Saved lane measurement complete; physical outcome unverified",
            "physical_failure_flags": {"detection_validated": False},
            "trace_reference": "trace.jsonl",
            "video_references": ["overview.mkv", "approach.mkv", "reference_corner.mkv",
                                 "driver_reference.mkv"],
            "video_frame_map_reference": "video_frames.jsonl",
            "recording_description": description,
            "recording_evidence": evidence,
            "realized_observables": realized,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    output = Path(args.output)
    if output.exists():
        raise ValueError("Retain prior lane analysis report")
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))


if __name__ == "__main__":
    main()
