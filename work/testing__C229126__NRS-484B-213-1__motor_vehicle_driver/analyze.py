"""Saved-only NRS 484B.213(1) descriptive finalizer.

Reads sealed original sources; never drives CARLA or decides legal judgments.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pass_measure import measure

SOURCES = ("pass-history.jsonl", "road-context.json", "native-result.json",
           "video_frames.jsonl", "reviewed-sources/map.source",
           "reviewed-sources/centerline.source")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def rows(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def measure_actor_scope(data):
    return {"ego_vehicle": True, "overtaken_vehicle": True,
            "oncoming_present": any("oncoming" in f["actors"] for f in data["frames"])}


def measure_highway_geometry(data):
    road = data["road"]
    return {"public_highway": road["public_highway"], "lane_count": road["lane_count"],
            "opposite_permitted_directions": road["opposite_permitted_directions"],
            "undivided": road["undivided"], "centerline_source": road["centerline_source"]}


def measure_left_pass(data):
    return {"left_of_center_frames": data["result"]["left_of_center_frames"],
            "ego_and_target_history_frames": data["result"]["original_frame_count"]}


def measure_visibility(data):
    samples = data["result"]["per_frame"]
    return {"clear_distance_m": [s["left_ray_clear_distance_min_m"] for s in samples],
            "opaque_hit_frames": [s["original_frame"] for s in samples if s["left_ray_any_occluded"]],
            "proxy": "incoming-lane virtual observer rays; not driver perception"}


def measure_oncoming(data):
    return {"forward_station_gap_m": [s["oncoming_forward_station_gap_m"]
                                      for s in data["result"]["per_frame"]],
            "judgment": "unresolved"}


def measure_completion(data):
    return {"pass_and_return_frame": data["result"]["measured_pass_and_return_frame"],
            "left_of_center_frames": data["result"]["left_of_center_frames"]}


def measure_opposite_response(data):
    return {"original_response_history": [s["oncoming_response"]
                                          for s in data["result"]["per_frame"]],
            "interference_judgment": "unresolved"}


def measure_overtaken_response(data):
    return {"original_speed_history_mps": [s["overtaken_speed_mps"]
                                           for s in data["result"]["per_frame"]],
            "interference_judgment": "unresolved"}


METHODS = (measure_actor_scope, measure_highway_geometry, measure_left_pass,
           measure_visibility, measure_oncoming, measure_completion,
           measure_opposite_response, measure_overtaken_response)


def analyze(root):
    root = Path(root)
    for name in SOURCES:
        required(root, name)
    history = rows(root / "pass-history.jsonl")
    mapping = rows(root / "video_frames.jsonl")
    if len(history) != len(mapping) or not history:
        raise ValueError("original history/frame-map join incomplete")
    for index, (body, frame) in enumerate(zip(history, mapping)):
        if body.get("original_frame") != index or body.get("carla_frame") != frame.get("carla_frame") or abs(body.get("time_s", -1)-frame.get("time_s", -2)) > 1e-6:
            raise ValueError("original body/frame-map identity mismatch")
    road = json.loads((root / "road-context.json").read_text())
    native = json.loads((root / "native-result.json").read_text())
    config = json.loads(required(root, "config.json").read_text())
    if native.get("recording_description") != config.get("case", {}).get("recording_description"):
        raise ValueError("original recording description differs from selected case")
    fixture_path = root / "fixture-provenance.json"
    is_fixture = fixture_path.is_file() and json.loads(fixture_path.read_text()).get("diagnostic_fixture") is True
    if not is_fixture and len(history) != config.get("duration_s", len(history))*20:
        raise ValueError("original episode duration incomplete")
    source_hashes = {name: sha(root / name) for name in SOURCES}
    if road.get("centerline_source_sha256") != source_hashes["reviewed-sources/centerline.source"]:
        raise ValueError("original centerline source bytes changed")
    road["centerline_source"] = source_hashes["reviewed-sources/centerline.source"]
    packet = {"format": "nrs-484b-213-1-native-projection",
              "source": {"native_result_sha256": source_hashes["native-result.json"],
                         "map_sha256": source_hashes["reviewed-sources/map.source"],
                         "frame_map_sha256": source_hashes["video_frames.jsonl"]},
              "road": road,
              "frames": [dict(row, ray_source_sha256=source_hashes["pass-history.jsonl"])
                         for row in history]}
    result = measure(packet)
    data = {"result": result, "road": road, "frames": history}
    measurements = {}
    for method in METHODS:
        name = method.__name__
        measurements[name] = {"value": method(data), "method": name,
                              "sources": dict(source_hashes)}
    report = {"format": "worker-analysis-report", "case_id": config["selected_case_id"],
              "measurements": measurements, "analysis_complete": True,
              "physical_acceptance_claimed": False,
              "limitations": ["Actual pixels and physical completion require independent local review.",
                              "Qualitative statutory judgments remain unresolved."]}
    return report, native


def channel_value(name, row, road):
    actors = row["actors"]
    ego, target = actors["ego"], actors["overtaken"]
    oncoming = actors.get("oncoming")
    if name == "highway_geometry":
        return {key: road[key] for key in
                ("public_highway", "lane_count", "opposite_permitted_directions", "undivided")}
    if name == "centerline_and_lane_directions":
        return {"centerline_source_sha256": road["centerline_source_sha256"],
                "lanes": road["lanes"]}
    if name == "driver_and_vehicle_identity":
        return {"ego_actor_id": ego["actor_id"], "overtaken_actor_id": target["actor_id"],
                "oncoming_actor_id": oncoming["actor_id"] if oncoming else "absent"}
    if name == "ego_target_oncoming_body_history":
        return actors
    if name == "pass_completion":
        return {"ego_left_body_edge_m": ego["centerline_signed_body_edge_m"],
                "ego_rear_station_m": ego["rear_station_m"],
                "overtaken_front_station_m": target["front_station_m"]}
    if name == "left_side_visibility":
        return row["left_side_rays"]
    if name == "oncoming_forward_distance":
        return {"present": bool(oncoming),
                "forward_station_gap_m": oncoming["station_m"]-ego["station_m"] if oncoming else "absent"}
    if name == "oncoming_start_gap_m":
        if oncoming is None:
            raise ValueError("oncoming gap channel requires original opposite-direction vehicle")
        return oncoming["station_m"]-ego["station_m"]
    if name == "opposite_vehicle_response":
        return {"present": bool(oncoming), "speed_mps": oncoming["speed_mps"] if oncoming else "absent",
                "lateral_m": oncoming["lateral_m"] if oncoming else "absent"}
    if name == "overtaken_vehicle_response":
        return {"speed_mps": target["speed_mps"], "lateral_m": target["lateral_m"]}
    if name == "original_frame_and_camera_join":
        return {"original_frame": row["original_frame"], "carla_frame": row["carla_frame"]}
    raise ValueError("unknown selected recording channel: " + name)


def write_channels(root, description):
    root = Path(root)
    history = rows(root / "pass-history.jsonl")
    road = json.loads((root / "road-context.json").read_text())
    folder = root / "channels"
    folder.mkdir(exist_ok=True)
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        path = folder / (name + ".jsonl")
        if path.exists():
            raise ValueError("derived channel already exists")
        with path.open("x") as stream:
            for row in history:
                stream.write(json.dumps({"time_s": row["time_s"],
                                         "value": channel_value(name, row, road)},
                                        allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(path.relative_to(root)),
                         "source_sha256": sha(path)})
    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report, native = analyze(args.attempt)
    from worker_exchange.native_output import physical_result, validate_result
    native["case_id"] = report["case_id"]
    native["measured_values"].update({key: item["value"] for key, item in report["measurements"].items()})
    native["recording_evidence"] = write_channels(args.attempt, native["recording_description"])
    native = physical_result(args.attempt, native)
    if any(c["name"] == "oncoming_start_gap_m" for c in native["recording_description"]["channels"]):
        observed = rows(args.attempt / "channels/oncoming_start_gap_m.jsonl")
        native["realized_observables"]["oncoming_start_gap_m"] = {
            "value": observed[0]["value"], "unit": "m",
            "method": "Original source-bound forward station gap samples; retain full history",
            "time_window": "first original frame of selected passing episode",
            "statistic": "first", "sample_window_s": [observed[0]["time_s"], observed[0]["time_s"]],
            "reference": "channels/oncoming_start_gap_m.jsonl"}
    validate_result(native)
    (args.attempt / "result.json").write_text(json.dumps(native, indent=2) + "\n")
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
