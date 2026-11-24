"""Build source-hashed current-runtime diagnostic recipes for the repaired lane.

All generated motion is synthetic. The recipe makes no Native or legal claim.
"""

import hashlib
import json
import os
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / ".runtime-work"
ASSIGNMENT = HERE.name


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n")


def write_rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n" for row in values))


def base_rows(label):
    construction = json.loads((HERE / "right-only-candidates" / label / "primary" / "construction.json").read_text())
    config = json.loads(next(file["content"] for file in construction["files"] if file["path"] == "config.json"))
    lane = -1 if label == "reference" else -2
    approach_y = 1.75 if label == "reference" else 5.25
    samples, original_trace, original_frames, original_evidence = [], [], [], []
    for index in range(480):
        if index < 160:
            x = -40 + 30 * index / 159
            road_id = 1
        elif index < 320:
            x = -9.5 + 16.8 * (index - 160) / 159
            road_id = 14
        else:
            x = 7.3 + 32.7 * (index - 320) / 159
            road_id = 2
        frame = index + 100
        time = .05 * (index + 1)
        corners = [[x + dx, approach_y + dy] for dx, dy in
                   ((-2.6, -1.1), (-2.6, 1.1), (2.6, 1.1), (2.6, -1.1))]
        sample = {"native_frame": frame, "time_s": time,
                  "native_center_xy_m": [x, approach_y], "native_forward_xy": [1, 0],
                  "native_body_xy_m": corners, "native_road_id": road_id,
                  "native_lane_id": lane}
        samples.append(sample)
        original_trace.append({"frame": frame, "heading_deg": 0})
        original_frames.append({"video_frame": index, "native_frame": frame,
                                "carla_frame": frame, "time_s": time})
        original_evidence.append({"original_frame": frame})
    return config, samples, original_trace, original_frames, original_evidence


def make_source(label):
    output = HERE / "current-fixture" / label
    output.mkdir(parents=True, exist_ok=True)
    config, samples, original_trace, original_frames, original_evidence = base_rows(label)
    lane = -1 if label == "reference" else -2
    trace, evidence, frames, graphs, history = [], [], [], [], []
    geometry = {"native_map_sha256": "a" * 64,
                "approach_road_id": 1, "straight_connector_road_id": 14,
                "straight_destination_road_id": 2, "right_only_lane_id": -2,
                "adjacent_through_lane_id": -1,
                "right_only_lane_native_y_bounds_m": [3.5, 7.0],
                "intersection_native_xy_bounds_m": [-7, -7, 7, 7],
                "right_only_lane_design_native_verified": False}
    channels = {row["name"]: [] for row in config["recording_description"]["channels"]}
    for index, (sample, row, frame, item) in enumerate(zip(samples, original_trace, original_frames, original_evidence)):
        source_frame, time = sample["native_frame"], sample["time_s"]
        x, y = sample["native_center_xy_m"]
        body = [[a, b, z] for a, b in sample["native_body_xy_m"] for z in (0, 1.5)]
        trace.append({"frame": source_frame, "time_s": time,
                      "position": {"x": x, "y": y, "z": 0.5},
                      "position_m": [x, y, 0.5], "heading_deg": row["heading_deg"],
                      "speed_mps": 5, "speed_mph": 5 / .44704,
                      "velocity_mps": [5, 0, 0],
                      "control": {"throttle": .3, "brake": 0, "hand_brake": False}})
        evidence.append({"original_frame": source_frame, "replay_frame": source_frame,
                         "actor_id": 107, "recording_time_s": time,
                         "replay_simulation_time_s": time,
                         "ego": {"position_m": [x, y, .5], "heading_deg": row["heading_deg"],
                                 "speed_mps": 5, "speed_provenance": "synthetic_native_sample",
                                 "body_vertices_m": body},
                         "world": {"weather": {"cloudiness": 0, "precipitation": 0,
                                               "wetness": 0, "fog_density": 0},
                                   "road_projection": {"road_id": sample["native_road_id"],
                                                       "section_id": 0, "lane_id": lane,
                                                       "s_m": x + 50}}})
        history.append({"frame": source_frame, "time_s": time,
                        "body_vertices_m": body})
        channel_values = {
            "drv.in_intersection": sample["native_road_id"] == 14,
            "st.intersection": geometry,
            "st.turn_lane": geometry,
            "rel.occupies": sample["native_body_xy_m"],
            "kin.heading": row["heading_deg"],
            "native_body_pose_control": sample,
            "camera_frame_join": frame,
        }
        for name, value in channel_values.items():
            channels[name].append({"time_s": time, "value": value})
        key = f"{source_frame:08d}"
        graph = {"path": f"capture/native/graphs/base/{key}.adapter.json",
                 "attributes": {"frame": source_frame, "simulation_time_s": time,
                                "synthetic_diagnostic": True},
                 "nodes": [{"id": "ego", "attributes": {"sem_class": "ego", "entity_id": 107,
                                                   "vertex": [x, y, .5], "forward": [1, 0, 0],
                                                   "threedbbox": body}}], "edges": []}
        graphs.append(graph)
        frames.append({"frame": source_frame, "simulation_time": time, "time_s": time,
                       "base": f"graphs/base/{key}.adapter.json",
                       "abstract": f"graphs/abstract/{key}.pkl",
                       "adapter_graph": f"graphs/base/{key}.adapter.json",
                       "synthetic_diagnostic": True})
        assert frame["native_frame"] == source_frame == item["original_frame"]
        assert index == frame["video_frame"]
    assert len(samples) == len(trace) == len(evidence) == len(frames) == 480
    write_rows(output / "native_samples.jsonl", samples)
    write_rows(output / "body_history.jsonl", history)
    write_rows(output / "trace.jsonl", trace)
    write_rows(output / "video_frames.jsonl", original_frames)
    write_rows(output / "capture/evidence.jsonl", evidence)
    write_rows(output / "capture/native/frames.jsonl", frames)
    for name, values in channels.items():
        write_rows(output / "source_channels" / (name + ".jsonl"), values)
    write_json(output / "road_geometry.json", geometry)
    write_json(output / "context.json", {"surveyed_right_turn_lane_intersection": geometry})
    (output / "road.xodr").write_bytes((HERE / "native/right_only_road.xodr").read_bytes())
    (output / "capture/recorder_info.txt").write_text("Create 107: vehicle.lincoln.mkz_2020\n")
    write_json(output / "capture/manifest.json", {
        "extraction_confirmed": True, "frames": 480,
        "acquisition": "synthetic_diagnostic", "observation_contract_version": 1,
        "required_observations": ["kin.position", "kin.heading"],
        "sources": {"road.xodr": digest(output / "road.xodr"),
                    "trace.jsonl": digest(output / "trace.jsonl")},
        "synthetic_diagnostic": True})
    write_json(output / "acquisition-provenance.json", {
        "provenance_kind": "synthetic_local_diagnostic", "diagnostic_fixture": True,
        "native_executed": False, "physical_acceptance_claimed": False})
    write_json(output / "context-scope.json", {
        "assignment_id": ASSIGNMENT, "case_id": ASSIGNMENT + "__" + label,
        "right_only_lane_id": -2, "selected_approach_lane_id": lane,
        "authored_road_sha256": digest(output / "road.xodr"),
        "native_lane_design_verified": False})
    source_entries = []
    for path in sorted(output.rglob("*")):
        if path.is_file():
            source_entries.append({"path": path.relative_to(output).as_posix(),
                                   "source": path.relative_to(ROOT).as_posix(),
                                   "sha256": digest(path)})
    videos = [{"path": camera["name"] + ".mkv", "frames": 480,
               "width": camera["width"], "height": camera["height"],
               "fps": 20, "color": "blue"} for camera in config["cameras"]]
    spec = HERE / f"current-{label}-diagnostic.json"
    write_json(spec, {"files": {}, "graphs": graphs, "videos": videos})
    recipe = HERE / f"current-{label}-recipe.json"
    write_json(recipe, {"format": "worker-fixture-recipe", "sources": source_entries,
                        "generator": {"source": spec.relative_to(ROOT).as_posix(),
                                      "sha256": digest(spec)}})
    return {"case": label, "sources": len(source_entries), "graphs": len(graphs),
            "recipe_sha256": digest(recipe)}


def main():
    output_root = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "/")).resolve()
    if SCRATCH.resolve() not in output_root.parents:
        raise SystemExit("Set SCENARIO_PIPELINE_OUTPUT_ROOT below .runtime-work")
    for label in ("reference", "contrast"):
        print(json.dumps(make_source(label), sort_keys=True))


if __name__ == "__main__":
    main()
