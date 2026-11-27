"""Saved-only bridge approach finalizer over original Native sources."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from bridge_measure import measure

SOURCES = ("bridge-history.jsonl", "road-context.json", "native-result.json",
           "video_frames.jsonl", "reviewed-sources/map.source",
           "reviewed-sources/centerline.source", "reviewed-sources/bridge.source")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]



def measure_vehicle_driver(measured):
    return {"ego_vehicle": True, "original_frames": len(measured["per_frame"])}


def measure_bridge_context(measured):
    return {"structure_type": "bridge", "bridge_entrance_station_m": measured["bridge_entrance_station_m"]}


def measure_left_side(measured):
    return {"left_body_edge_m": [row["left_body_edge_m"] for row in measured["per_frame"]],
            "body_crossing": [row["left_of_center_body"] for row in measured["per_frame"]]}


def measure_approach_distance(measured):
    return {"statutory_distance_m": measured["statutory_distance_m"],
            "front_center_rear_m": [[row["bridge_distance_front_m"], row["bridge_distance_center_m"], row["bridge_distance_rear_m"]] for row in measured["per_frame"]],
            "reference_unresolved": measured["distance_reference_unresolved"]}


def measure_view(measured):
    return {"ray_brackets": [row["ray_brackets"] for row in measured["per_frame"]],
            "view_obstructed_judgment": measured["view_obstructed_judgment"]}


def measure_one_way(measured):
    return {"one_way_highway": measured["one_way_highway"]}


METHODS = (measure_vehicle_driver, measure_bridge_context, measure_left_side,
           measure_approach_distance, measure_view, measure_one_way)

def analyze(root):
    root = Path(root)
    for name in SOURCES:
        required(root, name)
    history = rows(root / "bridge-history.jsonl")
    mapping = rows(root / "video_frames.jsonl")
    if not history or len(history) != len(mapping):
        raise ValueError("original bridge history/frame-map join incomplete")
    for index, (body, frame) in enumerate(zip(history, mapping)):
        if body.get("original_frame") != index or body.get("carla_frame") != frame.get("carla_frame") or abs(body.get("time_s", -1)-frame.get("time_s", -2)) > 1e-6:
            raise ValueError("original bridge frame-map identity mismatch")
    road = json.loads((root / "road-context.json").read_text())
    native = json.loads((root / "native-result.json").read_text())
    config = json.loads(required(root, "config.json").read_text())
    if native.get("recording_description") != config.get("case", {}).get("recording_description"):
        raise ValueError("original recording description differs from selected case")
    fixture = root / "fixture-provenance.json"
    is_fixture = fixture.is_file() and json.loads(fixture.read_text()).get("diagnostic_fixture") is True
    if not is_fixture and len(history) != config.get("duration_s", len(history))*20:
        raise ValueError("original bridge episode duration incomplete")
    hashes = {name: sha(root / name) for name in SOURCES}
    if road.get("centerline_source_sha256") != hashes["reviewed-sources/centerline.source"]:
        raise ValueError("original centerline source changed")
    if road.get("bridge_source_sha256") != hashes["reviewed-sources/bridge.source"]:
        raise ValueError("original bridge source changed")
    measured = measure({"road": road, "frames": history})
    measurements = {method.__name__: {"value": method(measured), "method": method.__name__,
                                      "sources": hashes} for method in METHODS}
    measurements["measure_bridge_approach"] = {"value": measured, "method": "measure_bridge_approach", "sources": hashes}
    report = {"format": "worker-analysis-report", "case_id": config["selected_case_id"],
              "measurements": measurements, "analysis_complete": True,
              "physical_acceptance_claimed": False,
              "limitations": ["Original pixels and actual obstruction require independent review.",
                              "Distance reference and view-obstruction judgment remain unresolved."]}
    return report, native


def channel_value(name, row, road):
    ego = row["actors"]["ego"]
    if name == "bridge_identity_and_entrance":
        return {key: road[key] for key in ("structure_type", "bridge_entrance_station_m", "bridge_source_sha256")}
    if name == "highway_directionality":
        return {key: road[key] for key in ("public_highway", "one_way_highway", "lanes")}
    if name == "vehicle_body_and_centerline":
        return {"ego": ego, "centerline_source_sha256": road["centerline_source_sha256"]}
    if name == "approach_progression":
        return {"station_m": ego["station_m"], "front_station_m": ego["front_station_m"]}
    if name == "bridge_distance_front_center_rear":
        entrance = road["bridge_entrance_station_m"]
        return {"front_m": entrance-ego["front_station_m"],
                "center_m": entrance-ego["station_m"],
                "rear_m": entrance-ego["rear_station_m"]}
    if name == "left_side_body_occupancy":
        return {"left_body_edge_m": ego["centerline_signed_body_edge_m"],
                "body_vertices_xy_m": ego["body_vertices_xy_m"]}
    if name == "view_ray_brackets":
        return row["left_side_rays"]
    if name == "original_frame_and_camera_join":
        return {"original_frame": row["original_frame"], "carla_frame": row["carla_frame"]}
    raise ValueError("unknown selected bridge channel: " + name)


def write_channels(root, description):
    root = Path(root)
    history = rows(root / "bridge-history.jsonl")
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
    validate_result(native)
    (args.attempt / "result.json").write_text(json.dumps(native, indent=2) + "\n")
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
