"""Build explicit synthetic saved-source recipes for all six C150041 cases.

Generated videos and telemetry test software only. They are never Native evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from parking_pose import REQUESTS, request


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def build(kind):
    activity = request(kind)[0]
    directory = ROOT / "diagnostic" / kind
    construction = json.loads((directory / "construction.json").read_text())
    scene = json.loads(next(item["content"] for item in construction["files"]
                            if item["path"] == "scene.json"))
    packet = json.loads((directory / "reviewed-context.json").read_text())
    if scene["case_id"] != ASSIGNMENT + "__" + kind or packet["context"]["activity"] != activity:
        raise ValueError("saved fixture case or activity changed")
    pose = scene["target_pose"]
    history = []
    for i, speed in enumerate((2.0, 0.2, 0.1, 0.0, 0.0)):
        history.append({"frame": i + 1, "time_s": (i + 1) / 20,
                        "body_vertices_xy_m": pose["target_body_vertices_xy_m"],
                        "vehicle_forward_xy": pose["target_forward_xy"],
                        "speed_m_s": speed,
                        "control": {"throttle": 0.0, "steer": 0.0, "brake": 1.0}})
    lines = lambda rows: "".join(json.dumps(row, allow_nan=False) + "\n" for row in rows)
    mapping = [{"video_frame": i, "carla_frame": i + 1, "time_s": (i + 1) / 20}
               for i in range(len(history))]
    camera_map = [{"frame": i + 1, "time_s": (i + 1) / 20,
                   "camera_names": list(scene["capture_plan"]["cameras"]),
                   "source_path": "video_frames.jsonl"} for i in range(len(history))]
    trace = [{"frame": row["frame"], "time_s": row["time_s"],
              "position": {"x": sum(point[0] for point in row["body_vertices_xy_m"]) / 4,
                           "y": sum(point[1] for point in row["body_vertices_xy_m"]) / 4,
                           "z": 0.0},
              "heading_deg": math.degrees(math.atan2(row["vehicle_forward_xy"][1],
                                                    row["vehicle_forward_xy"][0])),
              "speed_mps": row["speed_m_s"],
              "speed_mph": row["speed_m_s"] / 0.44704,
              "position_m": [sum(point[0] for point in row["body_vertices_xy_m"]) / 4,
                             sum(point[1] for point in row["body_vertices_xy_m"]) / 4, 0.0],
              "velocity_mps": [row["vehicle_forward_xy"][0] * row["speed_m_s"],
                               row["vehicle_forward_xy"][1] * row["speed_m_s"], 0.0],
              "control": row["control"]} for row in history]
    road = (ROOT / "diagnostic-road.xodr").read_text()
    trace_text = lines(trace)
    evidence = []
    graph_index = []
    graphs = []
    for row, point in zip(history, trace):
        frame, time_s = row["frame"], row["time_s"]
        observations = {"frame": frame, "time_s": time_s, "participants": [],
                        "map_context": {"declared_public_way_road_ids": []}}
        body3 = [[x, y, z] for x, y in row["body_vertices_xy_m"] for z in (0.0, 1.5)]
        evidence.append({"actor_id": 7,
                         "ego": {"body_vertices_m": body3,
                                 "heading_deg": point["heading_deg"],
                                 "position_m": [point["position"]["x"],
                                                point["position"]["y"], 0.0],
                                 "speed_mps": point["speed_mps"],
                                 "speed_provenance": "synthetic_native_sample"},
                         "original_frame": frame, "original_observations": observations,
                         "recording_time_s": time_s, "replay_frame": frame,
                         "replay_simulation_time_s": time_s, "world": {"weather": {}}})
        graph_path = f"capture/native/graphs/base/{frame:08d}.adapter.json"
        graph_index.append({"adapter_graph": graph_path.removeprefix("capture/native/"),
                            "frame": frame, "simulation_time": time_s})
        graphs.append({"path": graph_path,
                       "attributes": {"frame": frame, "time_s": time_s,
                                      "observed_evidence": observations},
                       "nodes": [], "edges": []})
    spec = {"files": {"parking-history.jsonl": lines(history),
                       "video_frames.jsonl": lines(mapping),
                       "camera-frame-map.jsonl": lines(camera_map),
                       "trace.jsonl": trace_text,
                       "road.xodr": road,
                       "capture/evidence.jsonl": lines(evidence),
                       "capture/native/frames.jsonl": lines(graph_index),
                       "capture/recorder_info.txt": "Create 7: vehicle.tesla.model3 (parking diagnostic) at (0, 2.5, 0)\n",
                       "capture/manifest.json": json.dumps({
                           "acquisition": "original_live_run", "case_id": scene["case_id"],
                           "complete_driving_lanes": False, "extraction_confirmed": True,
                           "frames": len(history), "status": "draft",
                           "sources": {"road.xodr": hashlib.sha256(road.encode()).hexdigest(),
                                       "trace.jsonl": hashlib.sha256(trace_text.encode()).hexdigest()}}) + "\n",
                       "acquisition-provenance.json": json.dumps({
                           "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
                           "scope": "software only; no physical or legal acceptance"}) + "\n"},
            "graphs": graphs,
            "videos": [{"path": name + ".mkv", "frames": len(history),
                        "width": 1920 if name == "overview" else 1280,
                        "height": 1080 if name == "overview" else 720,
                        "fps": 20, "color": "black"}
                       for name in scene["capture_plan"]["cameras"]]}
    spec_path = directory / "saved-fixture-spec.json"
    _write(spec_path, spec)
    sources = []
    for relative in ("reviewed-context.json", *(v["path"] for v in packet["sources"].values())):
        source = directory / relative
        sources.append({"path": relative, "source": source.relative_to(REPO).as_posix(),
                        "sha256": _sha(source)})
    recipe = {"format": "worker-fixture-recipe", "sources": sources,
              "generator": {"source": spec_path.relative_to(REPO).as_posix(),
                            "sha256": _sha(spec_path)}}
    recipe_path = directory / "saved-fixture-recipe.json"
    _write(recipe_path, recipe)
    return recipe_path


if __name__ == "__main__":
    for kind in REQUESTS:
        print(build(kind))
