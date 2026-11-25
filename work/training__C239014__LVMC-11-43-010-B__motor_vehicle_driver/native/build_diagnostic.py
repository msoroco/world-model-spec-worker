"""Create bounded public compatibility inputs from source-shaped CPU fixtures."""
import hashlib
import json
from pathlib import Path
import tempfile

from prove_finalize import create

HERE = Path(__file__).resolve().parent
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def compact(value):
    return json.dumps(value, separators=(",", ":"), allow_nan=False)


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def build(condition):
    with tempfile.TemporaryDirectory(dir=HERE.parents[2] / ".runtime-work",
                                     prefix="c239014-source-") as temporary:
        root = Path(temporary)
        create(root, condition)
        files = {name: (root / name).read_text() for name in
            ("native-raw-actors.jsonl", "control-intent.jsonl", "video_frames.jsonl",
             "trace.jsonl", "roundabout-map-readback.json", "road.xodr",
             "acquisition-provenance.json")}
    actors = [json.loads(line) for line in files["native-raw-actors.jsonl"].splitlines()]
    maps = [json.loads(line) for line in files["video_frames.jsonl"].splitlines()]
    traces = []
    capture = []
    native = []
    graphs = []
    for row, mapping in zip(actors, maps):
        i, t, frame = mapping["video_frame"], mapping["time_s"], mapping["native_frame"]
        ego = next(a for a in row["actors"] if a["role"] == "ego")
        x, y, speed = ego["x_m"], ego["y_m"], ego["speed_mps"]
        vertices = [[x + dx, y + dy, z] for dx in (-2, 2)
                    for dy in (-1, 1) for z in (-.7, .7)]
        participant = {"actor_id": 1, "blueprint": "vehicle.synthetic.cpu",
                       "body_vertices_m": vertices, "heading_deg": 0,
                       "velocity_mps": [speed, 0, 0], "speed_mps": speed,
                       "accel_longitudinal_mps2": 0.0}
        observed = {"frame": frame, "time_s": t, "participants": [participant],
                    "world_settings": {"no_rendering_mode": False},
                    "rgb_sensors": {camera: {"frame": i} for camera in CAMERAS}}
        graph_path = f"graphs/base/{i:08d}.adapter.json"
        graphs.append({"path": "capture/native/" + graph_path,
                       "attributes": {"frame": i, "observed_evidence": observed},
                       "nodes": [], "edges": []})
        native.append({"frame": i, "time_s": t, "simulation_time": t,
                       "base": graph_path, "adapter_graph": graph_path})
        capture.append({"original_frame": frame, "replay_frame": i,
                        "actor_id": 1, "recording_time_s": t,
                        "replay_simulation_time_s": t,
                        "ego": {"position_m": [x, y, 0], "heading_deg": 0,
                                "speed_mps": speed, "speed_provenance": "synthetic_native_sample",
                                "body_vertices_m": vertices},
                        "world": {"weather": {"cloudiness": 0, "precipitation": 0,
                                              "wetness": 0, "fog_density": 0},
                                  "road_projection": {"road_id": ego["road_id"],
                                                      "section_id": 0, "lane_id": -1,
                                                      "s_m": float(i) / 20}},
                        "original_observations": observed})
        traces.append({"frame": frame, "time_s": t,
                       "position": {"x": x, "y": y, "z": 0},
                       "position_m": [x, y, 0], "heading_deg": 0,
                       "speed_mps": speed, "speed_mph": speed / .44704,
                       "velocity_mps": [speed, 0, 0], "control": {}})
    files["trace.jsonl"] = "".join(compact(row) + "\n" for row in traces)
    files["capture/evidence.jsonl"] = "".join(compact(row) + "\n" for row in capture)
    files["capture/native/frames.jsonl"] = "".join(compact(row) + "\n" for row in native)
    files["capture/recorder_info.txt"] = "Create 1: vehicle.synthetic.cpu (0) at (0,-48,0)\nSynthetic CPU diagnostic; no CARLA recorder\n"
    files["capture/manifest.json"] = compact({
        "extraction_confirmed": True, "frames": 600,
        "acquisition": "synthetic_cpu_fixture", "observation_contract_version": 2,
        "required_observations": [],
        "sources": {"road.xodr": sha(files["road.xodr"]),
                    "trace.jsonl": sha(files["trace.jsonl"])}}) + "\n"
    videos = [{"path": camera + ".mkv", "frames": 600,
               "width": 1920 if camera == "overview" else 1280,
               "height": 1080 if camera == "overview" else 720,
               "fps": 20, "color": color} for camera, color in zip(
                   CAMERAS, ("blue", "green", "white", "red"))]
    diagnostic = {"files": files, "graphs": graphs, "videos": videos}
    path = HERE.parent / ("diagnostic-" + condition + ".json")
    path.write_text(compact(diagnostic) + "\n")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Diagnostic source exceeds 2 MiB")
    repo = HERE.parents[2]
    rel = str(path.relative_to(repo))
    recipe = {"format": "worker-fixture-recipe",
              "sources": [{"path": "diagnostic-input.json", "source": rel,
                           "sha256": sha(path.read_text())}],
              "generator": {"source": rel, "sha256": sha(path.read_text())}}
    (HERE.parent / ("diagnostic-" + condition + "-recipe.json")).write_text(
        json.dumps(recipe, indent=2) + "\n")
    return {"condition": condition, "bytes": path.stat().st_size,
            "sha256": sha(path.read_text())}


if __name__ == "__main__":
    print(json.dumps([build(condition) for condition in ("condition_a", "condition_b")],
                     indent=2))
