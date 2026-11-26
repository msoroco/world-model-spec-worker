"""Generate small textual CPU-only source specifications for both exact cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from geometry import open_drive


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent.name
BASE = ASSIGNMENT + "__selected_1290826d__condition_"
GEOMETRY = {"native_map_sha256": "diagnostic-map-only",
            "native_map_object_readback": True,
            "crosswalk": {"near_x_m": 0.0, "width_along_road_m": 3.6576,
                          "low_y_m": -3.5, "high_y_m": 3.5,
                          "marked_yellow": True},
            "school_xing_sign": {"legend": "School-Xing", "x_m": -35.0,
                                  "native_map_object_present": True,
                                  "displayed_pixels_verified": False}}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(rows) -> str:
    return "".join(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n"
                   for row in rows)


def build(suffix: str) -> dict:
    if suffix not in ("a", "b"):
        raise ValueError("Unknown exact school-crossing condition")
    case = BASE + suffix
    native = []
    mapping = []
    trace = []
    body = []
    evidence = []
    frame_index = []
    graphs = []
    for index in range(600):
        frame = 10000 + index
        t = index / 20
        if suffix == "a":
            front = -12 + index * .05
        else:
            front = -12 + min(index, 160) * .05 + max(0, index - 340) * .05
        ped_y = -1.0 if suffix == "a" else -4.0
        corners = [[front, -3], [front, -.5], [front - 4, -.5], [front - 4, -3]]
        native.append({"native_frame": frame, "time_s": t,
                       "source_kind": "synthetic_native_sample",
                       "ego_body_xy_m": corners,
                       "person": {"actor_id": 11, "actor_kind": "walker",
                                  "center_x_m": 1.0, "center_y_m": ped_y,
                                  "velocity_y_mps": .5 if suffix == "a" else 0.0}})
        mapping.append({"video_frame": index, "carla_frame": frame,
                        "native_frame": frame, "time_s": t,
                        "camera_frames": {name: frame for name in
                                          ("overview", "approach", "reference_corner",
                                           "driver_reference")}})
        trace.append({"frame": frame, "time_s": t,
                      "position_m": [front - 2, -1.75, 0],
                      "position": {"x": front - 2, "y": -1.75, "z": 0},
                      "heading_deg": 0.0, "speed_mps": 1.0,
                      "speed_mph": 1.0 / .44704})
        body.append({"frame": frame, "time_s": t,
                     "body_vertices_m": corners, "pedestrian_actor_id": 11})
        vehicle = {"actor_id": 10, "blueprint": "vehicle.tesla.model3",
                   "position_m": [front - 2, -1.75, 0], "heading_deg": 0,
                   "velocity_mps": [1, 0, 0], "speed_mps": 1,
                   "body_vertices_m": [[x, y, 0] for x, y in corners]}
        walker = {"actor_id": 11, "blueprint": "walker.pedestrian.0001",
                  "position_m": [1, ped_y, 0], "heading_deg": 90,
                  "velocity_mps": [0, .5 if suffix == "a" else 0, 0],
                  "speed_mps": .5 if suffix == "a" else 0,
                  "body_vertices_m": [[1, ped_y, 0]]}
        original = {"frame": frame, "time_s": t, "participants": [vehicle, walker],
                    "relations": [], "devices": [],
                    "participant_inventory": "all two synthetic diagnostic actors",
                    "world_settings": {"no_rendering_mode": False},
                    "rgb_sensors": [{"actor_id": 20, "blueprint": "sensor.camera.rgb"}],
                    "map_context": {"declared_public_way_road_ids": []}}
        evidence.append({"original_frame": frame, "replay_frame": frame,
                         "actor_id": 10, "recording_time_s": t,
                         "replay_simulation_time_s": t,
                         "ego": {"position_m": vehicle["position_m"],
                                 "heading_deg": 0, "speed_mps": 1,
                                 "speed_provenance": "synthetic_native_sample",
                                 "body_vertices_m": vehicle["body_vertices_m"]},
                         "world": {"road_projection": {"road_id": 1,
                                                       "section_id": 0,
                                                       "lane_id": -1,
                                                       "s_m": 100 + front - 2}},
                         "timing": {}, "visibility": None,
                         "supporting_only": {},
                         "original_observations": original})
        graph_path = f"graphs/base/{frame:08d}.adapter.json"
        frame_index.append({"frame": frame, "simulation_time": t,
                            "abstract": None, "base": None, "nodes": 1,
                            "edges": 0, "extraction_seconds": 0,
                            "capture_seconds": 0,
                            "adapter_graph": graph_path})
        graphs.append({"path": "capture/native/" + graph_path,
                       "attributes": {"frame": frame, "simulation_time_s": t,
                                      "observed_evidence": {"frame": frame,
                                                            "time_s": t,
                                                            "participants": [],
                                                            "relations": []},
                                      "units": {"position": "m", "carla_speed": "m/s"}},
                       "nodes": [{"id": "ego", "attributes": {
                           "vertex": vehicle["position_m"], "sem_class": "ego",
                           "entity_id": 10, "carla_speed": 1,
                           "original_observation": vehicle}}],
                       "edges": []})
    road = open_drive()
    trace_text = lines(trace)
    capture_manifest = {"status": "draft", "acquisition": "synthetic_fixture",
                        "case_id": case, "source_run": "c394563 CPU diagnostic",
                        "map": "OpenDriveMap", "frames": 600,
                        "required_observations": [],
                        "extraction_confirmed": True,
                        "sources": {"road.xodr": hashlib.sha256(road.encode()).hexdigest(),
                                    "trace.jsonl": hashlib.sha256(trace_text.encode()).hexdigest()},
                        "complete_driving_lanes": False,
                        "observation_contract_version": 2,
                        "road_user_visibility_observed": False}
    spec = {"files": {
        "fixture-provenance.json": json.dumps({
            "scope": "CPU diagnostic only; synthetic actor and video source, never physical evidence",
            "frames": 600}),
        "road_geometry.json": json.dumps(GEOMETRY),
        "native_samples.jsonl": lines(native),
        "video_frames.jsonl": lines(mapping),
        "trace.jsonl": trace_text,
        "body_history.jsonl": lines(body),
        "road.xodr": road,
        "capture/manifest.json": json.dumps(capture_manifest),
        "capture/evidence.jsonl": lines(evidence),
        "capture/native/frames.jsonl": lines(frame_index),
        "capture/recorder_info.txt": "Version: 1\nMap: OpenDriveMap\n Create 10: vehicle.tesla.model3 (0) at (0, 0, 0)\nSynthetic diagnostic fixture; no CARLA recorder.\n"},
        "graphs": graphs,
        "videos": [{"path": name + ".mkv", "frames": 600,
                    "width": 1920 if name == "overview" else 1280,
                    "height": 1080 if name == "overview" else 720,
                    "fps": 20, "color": "black"} for name in
                   ("overview", "approach", "reference_corner", "driver_reference")]}
    path = HERE / ("diagnostic-condition-" + suffix + ".json")
    path.write_text(json.dumps(spec, separators=(",", ":"), ensure_ascii=False) + "\n")
    relative = "work/" + ASSIGNMENT + "/native/" + path.name
    recipe = {"format": "worker-fixture-recipe",
              "sources": [{"path": "diagnostic-input.json", "source": relative,
                           "sha256": sha(path)}],
              "generator": {"source": relative, "sha256": sha(path)}}
    recipe_path = HERE / ("recipe-condition-" + suffix + ".json")
    recipe_path.write_text(json.dumps(recipe, indent=2) + "\n")
    return {"case_id": case, "spec": str(path), "spec_sha256": sha(path),
            "recipe": str(recipe_path), "recipe_sha256": sha(recipe_path)}


if __name__ == "__main__":
    print(json.dumps([build("a"), build("b")], indent=2))
