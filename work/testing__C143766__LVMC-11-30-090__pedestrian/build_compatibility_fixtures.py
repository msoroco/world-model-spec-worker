"""Build bounded, explicitly synthetic five-frame compatibility fixtures.

These test finalization and conversion protocols. They do not stand in for a
Native acquisition or for reviewed sidewalk and trail context.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, allow_nan=False)+"\n"


def lines(values):
    return "".join(encoded(value) for value in values)


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+"\n")


def make(suffix):
    folder = HERE/"cases"/suffix
    scene = json.loads((folder/"scene.json").read_text())
    bodies = [json.loads(line) for line in
              (folder/"diagnostic-body-history.jsonl").read_text().splitlines()[:5]]
    if len(bodies) != 5:
        raise ValueError("five distinct diagnostic walker samples required")
    trace = []
    mapping = []
    joins = []
    evidence = []
    graph_frames = []
    graphs = []
    for i, body in enumerate(bodies):
        x = sum(point[0] for point in body["body_xy_m"])/4
        y = sum(point[1] for point in body["body_xy_m"])/4
        t = body["time_s"]
        rect = body["body_xy_m"]
        eight = [[p[0], p[1], z] for p in rect for z in (0.0, 1.8)]
        trace.append({"frame": i, "time_s": t, "position": {"x": x, "y": y, "z": 0.0},
                      "position_m": [x, y, 0.0], "heading_deg": 0.0,
                      "speed_mps": 1.2, "speed_mph": 1.2/.44704,
                      "velocity_mps": [1.2, 0.0, 0.0], "control": {}})
        mapping.append({"video_frame": i, "carla_frame": i,
                        "native_frame": i, "time_s": t})
        joins.append({"case_id": scene["case_id"], "frame": i, "time_s": t,
                      "walker_actor_id": 7, "cameras": {
                          name: {"frame": i, "width": width, "height": height,
                                 "pixel_format": "bgra", "bytes": width*height*4}
                          for name, width, height in CAMERAS}})
        observations = {"frame": i, "time_s": t,
                        "map_context": {"declared_public_way_road_ids": []},
                        "participants": []}
        evidence.append({"actor_id": 7, "ego": {
            "body_vertices_m": eight, "heading_deg": 0.0,
            "position_m": [x, y, 0.0], "speed_mps": 1.2,
            "speed_provenance": "synthetic_native_sample"},
            "original_frame": i, "original_observations": observations,
            "recording_time_s": t, "replay_frame": i,
            "replay_simulation_time_s": t, "world": {"weather": {}}})
        graph_path = f"capture/native/graphs/base/{i:08d}.adapter.json"
        graph_frames.append({"adapter_graph": f"graphs/base/{i:08d}.adapter.json",
                             "frame": i, "simulation_time": t})
        graphs.append({"path": graph_path,
                       "attributes": {"frame": i, "time_s": t,
                                      "observed_evidence": observations},
                       "nodes": [], "edges": []})
    files = {"acquisition-provenance.json": encoded({
                "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
                "scope": "software-only; no physical or legal acceptance"}),
             "walker-body-history.jsonl": lines(bodies),
             "trace.jsonl": lines(trace),
             "video_frames.jsonl": lines(mapping),
             "camera-frame-joins.jsonl": lines(joins),
             "capture/evidence.jsonl": lines(evidence),
             "capture/native/frames.jsonl": lines(graph_frames),
             "capture/recorder_info.txt": "Create 7: walker.pedestrian (synthetic diagnostic)\n"}
    road_hash = sha((HERE/"candidate-corridor.xodr").read_bytes())
    files["capture/manifest.json"] = encoded({
        "acquisition": "original_live_run", "case_id": scene["case_id"],
        "complete_driving_lanes": False, "extraction_confirmed": True,
        "frames": 5, "status": "draft",
        "sources": {"road.xodr": road_hash,
                    "trace.jsonl": sha(files["trace.jsonl"].encode())}})
    files["acquisition.json"] = encoded({name: {
        "kind": "diagnostic_fixture", "sha256": sha(content.encode())}
        for name, content in files.items() if name in (
            "walker-body-history.jsonl", "trace.jsonl", "video_frames.jsonl",
            "camera-frame-joins.jsonl")})
    spec = {"files": files, "graphs": graphs,
            "videos": [{"color": "black", "fps": 20, "frames": 5,
                        "height": height, "path": name+".mkv", "width": width}
                       for name, width, height in CAMERAS]}
    spec_path = folder/"diagnostic.json"
    write(spec_path, spec)
    note_path = folder/"diagnostic-source-note.json"
    write(note_path, {"case_id": scene["case_id"],
                      "source_kind": "synthetic_software_fixture",
                      "body_history_source": str((folder/"diagnostic-body-history.jsonl").relative_to(REPO)),
                      "body_history_sha256": sha((folder/"diagnostic-body-history.jsonl").read_bytes()),
                      "native_or_legal_acceptance_claimed": False})
    recipe = {"format": "worker-fixture-recipe", "sources": [
        {"path": "road.xodr", "source": str((HERE/"candidate-corridor.xodr").relative_to(REPO)),
         "sha256": road_hash},
        {"path": "diagnostic-source-note.json", "source": str(note_path.relative_to(REPO)),
         "sha256": sha(note_path.read_bytes())}],
        "generator": {"source": str(spec_path.relative_to(REPO)),
                      "sha256": sha(spec_path.read_bytes())}}
    write(folder/"fixture-recipe.json", recipe)
    return {"case_id": scene["case_id"], "recipe": str((folder/"fixture-recipe.json").relative_to(REPO)),
            "recipe_sha256": sha((folder/"fixture-recipe.json").read_bytes())}


if __name__ == "__main__":
    print(json.dumps([make(s) for s in ("roadway_walk", "sidewalk_walk", "shoulder_walk")], indent=2))
