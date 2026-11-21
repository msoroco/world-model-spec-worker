"""Measure other-first median-opening entry while ego approaches.

This preserves Native junction/highway identity, source frames and the Off
signal qualification. Entry order and speed are observations, not a legal yield
or statutory intersection determination.
"""

import hashlib
import json
import math
import argparse
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon


REQUIRED = ("crossing_history.jsonl", "video_frames.jsonl", "junction_context.json")


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Missing finite Native observation")
    return float(value)


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _inside(actor, polygon):
    vertices = actor.get("body_vertices_xy_m")
    if not isinstance(vertices, list) or len(vertices) < 4:
        raise ValueError("Missing complete actor body")
    body = MultiPoint([(_number(v[0]), _number(v[1])) for v in vertices]).convex_hull
    return body.intersects(polygon)


def analyze(root: Path, *, signal_mode: str = "off", allow_other_initially_inside: bool = False) -> dict:
    if signal_mode not in ("off", "operating"):
        raise ValueError("Unknown signal mode")
    root = Path(root)
    sources = {}
    for name in REQUIRED:
        path = root / name
        if not path.is_file():
            raise ValueError("Missing required source: " + name)
        sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    context = json.loads((root / "junction_context.json").read_text())
    for key in ("native_map_id", "intersection_id", "ego_highway_id", "other_highway_id",
                "ego_road_id", "other_road_id", "native_signal_id", "signal_governance_source",
                "signal_head_video_source", "intersection_polygon_source"):
        if context.get(key) is None:
            raise ValueError("Missing sourced crossing context: " + key)
    if context["ego_highway_id"] == context["other_highway_id"]:
        raise ValueError("Approaches must be from different highways")
    if context.get("installed_uncovered_vehicular_heads") is not True:
        raise ValueError("Uncovered vehicular signal heads not sourced")
    vertices = context.get("intersection_polygon_xy_m")
    if not isinstance(vertices, list) or len(vertices) < 3:
        raise ValueError("Missing sourced intersection polygon")
    polygon = Polygon([(_number(v[0]), _number(v[1])) for v in vertices])
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("Invalid intersection polygon")
    rows, frames = _rows(root / "crossing_history.jsonl"), _rows(root / "video_frames.jsonl")
    if len(rows) < 3 or len(rows) != len(frames):
        raise ValueError("Incomplete crossing/frame history")
    prior = (-1, -math.inf)
    first_entry = {"ego": None, "other": None}
    prior_inside = {"ego": False, "other": False}
    occupancy = {"ego": [], "other": []}
    observed_signal_states = []
    other_initially_inside = False
    samples = []
    for index, (row, frame) in enumerate(zip(rows, frames)):
        fid, time = row.get("frame"), _number(row.get("time_s"))
        if type(fid) is not int or fid <= prior[0] or time <= prior[1]:
            raise ValueError("Nonmonotone original frame/time")
        prior = (fid, time)
        if frame.get("video_frame") != index or frame.get("carla_frame") != fid or frame.get("time_s") != time:
            raise ValueError("Original video frame join failed")
        if row.get("native_signal_id") != context["native_signal_id"]:
            raise ValueError("Identified signal source changed")
        state = row.get("signal_state")
        if signal_mode == "off" and state != "Off":
            raise ValueError("Identified signal not observed Off")
        if signal_mode == "operating" and state not in ("Red", "Yellow", "Green"):
            raise ValueError("Identified signal not observed operating")
        observed_signal_states.append(state)
        sample = {"frame": fid, "time_s": time}
        for who in ("ego", "other"):
            actor = row.get(who)
            if not isinstance(actor, dict) or actor.get("intersection_id") != context["intersection_id"] or actor.get("road_id") != context[who + "_road_id"]:
                raise ValueError("Actor not on sourced junction approach")
            inside = _inside(actor, polygon)
            if index == 0 and inside:
                if who != "other" or not allow_other_initially_inside:
                    raise ValueError("No observed pre-entry approach")
                other_initially_inside = True
            distance = _number(actor.get("distance_to_intersection_m"))
            speed = _number(actor.get("speed_mps"))
            if distance < 0 or speed < 0:
                raise ValueError("Invalid approach distance or speed")
            if inside and not prior_inside[who] and first_entry[who] is None and not (index == 0 and who == "other"):
                first_entry[who] = {"frame": fid, "time_s": time}
            if inside and not prior_inside[who]:
                occupancy[who].append({"entry_frame": None if index == 0 else fid,
                                       "entry_time_s": None if index == 0 else time,
                                       "exit_frame": None, "exit_time_s": None})
            if not inside and prior_inside[who]:
                occupancy[who][-1]["exit_frame"] = fid
                occupancy[who][-1]["exit_time_s"] = time
            prior_inside[who] = inside
            sample[who] = {"body_in_intersection": inside, "distance_to_intersection_m": distance,
                           "speed_mps": speed}
        samples.append(sample)
    if (first_entry["other"] is None and not other_initially_inside) or first_entry["ego"] is None:
        raise ValueError("Required body entry not observed")
    other_frame = first_entry["other"]["frame"] if first_entry["other"] else None
    other_index = next((i for i, sample in enumerate(samples) if sample["frame"] == other_frame), None)
    ego_approaching_at_other_entry = (other_index is not None and not samples[other_index]["ego"]["body_in_intersection"]
        and samples[other_index]["ego"]["distance_to_intersection_m"] > 0
        and other_index + 1 < len(samples)
        and samples[other_index + 1]["ego"]["distance_to_intersection_m"] < samples[other_index]["ego"]["distance_to_intersection_m"])
    ego_speeds_while_other_inside = [sample["ego"]["speed_mps"] for sample in samples
                                     if sample["other"]["body_in_intersection"] and not sample["ego"]["body_in_intersection"]]
    other_inside_while_ego_outside = [sample for sample in samples
                                      if sample["other"]["body_in_intersection"] and
                                      not sample["ego"]["body_in_intersection"]]
    return {"format": "worker-median-opening-crossing-observations", "sources": sources,
            "intersection_id": context["intersection_id"],
            "highway_ids": [context["ego_highway_id"], context["other_highway_id"]],
            "signal_mode": signal_mode,
            "observed_signal_states": observed_signal_states,
            "first_body_entry": first_entry,
            "other_initially_inside_observed": other_initially_inside,
            "occupancy_intervals": occupancy,
            "other_entered_before_ego_observed": (first_entry["other"]["time_s"] < first_entry["ego"]["time_s"]
                                                if first_entry["other"] else None),
            "ego_approaching_at_other_entry_observed": ego_approaching_at_other_entry,
            "minimum_ego_speed_while_other_inside_mps": min(ego_speeds_while_other_inside) if ego_speeds_while_other_inside else None,
            "ego_speed_samples_while_other_inside": [{"frame": sample["frame"],
                                                       "time_s": sample["time_s"],
                                                       "speed_mps": sample["ego"]["speed_mps"]}
                                                      for sample in other_inside_while_ego_outside],
            "ego_entered_while_other_inside_observed": any(sample["ego"]["body_in_intersection"] and
                                                          sample["other"]["body_in_intersection"]
                                                          for sample in samples),
            "other_exit_observed": occupancy["other"][-1]["exit_frame"] is not None,
            "samples": samples,
            "statutory_roadway_crossing_judgment": "unresolved",
            "statutory_inoperative_signal_judgment": "unresolved",
            "right_of_way_judgment": "unresolved"}


def main():
    parser = argparse.ArgumentParser(description="Finalize saved median-opening crossing observations")
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("--signal-mode", choices=("off", "operating"), default="off")
    parser.add_argument("--allow-other-initially-inside", action="store_true")
    args = parser.parse_args()
    result = analyze(args.source_dir, signal_mode=args.signal_mode,
                     allow_other_initially_inside=args.allow_other_initially_inside)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
