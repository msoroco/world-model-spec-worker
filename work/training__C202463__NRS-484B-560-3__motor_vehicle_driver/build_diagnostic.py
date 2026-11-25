"""Build bounded source-shaped public CPU fixtures for five rail-stop cases."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "native"))
from prove_finalizer_source import fixture

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def compact(value):
    return json.dumps(value, separators=(",", ":"), allow_nan=False)


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def build(suffix):
    with tempfile.TemporaryDirectory(dir=ROOT / ".runtime-work",
                                     prefix="c202463-source-") as temporary:
        folder = Path(temporary) / suffix
        fixture(folder, suffix)
        files = {str(path.relative_to(folder)): path.read_text()
                 for path in folder.rglob("*") if path.is_file() and path.name not in
                 ("config.json", *(name + ".mkv" for name in CAMERAS))}
    actors = [json.loads(line) for line in files["actors.jsonl"].splitlines()]
    gates = [json.loads(line) for line in files["gate.jsonl"].splitlines()]
    maps = [json.loads(line) for line in files["video_frames.jsonl"].splitlines()]
    capture, native, graphs, traces = [], [], [], []
    for row, gate, mapping in zip(actors, gates, maps):
        i, t, frame = mapping["video_frame"], mapping["time_s"], mapping["native_frame"]
        participants = []
        for actor_id, label in ((1, "ego"), (2, "other")):
            actor = row["actors"][label]
            x, y = actor["x_m"], actor["y_m"]
            vertices = ([[xx, yy, z] for xx in (x - 2.25, x + 2.25)
                         for yy in (y - .9, y + .9) for z in (-.7, .7)]
                        if label == "ego" else [[x - 2.25, y - .9, 0],
                                                [x + 2.25, y + .9, 0]])
            participants.append({"actor_id": actor_id, "blueprint": "vehicle.synthetic.cpu",
                "body_vertices_m": vertices, "heading_deg": 0,
                "velocity_mps": [0, 0, 0], "speed_mps": actor["speed_mps"],
                "accel_longitudinal_mps2": 0.0})
        observed = {"frame": frame, "time_s": t, "participants": participants,
            "world_settings": {"no_rendering_mode": False},
            "rgb_sensors": {camera: {"frame": i} for camera in CAMERAS}}
        graph_path = f"graphs/base/{i:08d}.adapter.json"
        graphs.append({"path": "capture/native/" + graph_path,
            "attributes": {"frame": i, "observed_evidence": observed},
            "nodes": [], "edges": []})
        native.append({"frame": i, "time_s": t, "simulation_time": t,
            "base": graph_path, "adapter_graph": graph_path})
        ego = row["actors"]["ego"]
        capture.append({"original_frame": frame, "replay_frame": i,
            "actor_id": 1, "recording_time_s": t, "replay_simulation_time_s": t,
            "ego": {"position_m": [ego["x_m"], ego["y_m"], 0],
                "heading_deg": 0, "speed_mps": ego["speed_mps"],
                "speed_provenance": "synthetic_native_sample",
                "body_vertices_m": participants[0]["body_vertices_m"]},
            "world": {"weather": {"cloudiness": 0, "precipitation": 0,
                                  "wetness": 0, "fog_density": 0},
                      "road_projection": {"road_id": 1, "section_id": 0,
                                          "lane_id": -1, "s_m": i / 20}},
            "original_observations": observed})
        traces.append({"frame": frame, "time_s": t,
            "position": {"x": ego["x_m"], "y": ego["y_m"], "z": 0},
            "position_m": [ego["x_m"], ego["y_m"], 0],
            "heading_deg": 0, "speed_mps": ego["speed_mps"],
            "speed_mph": ego["speed_mps"] / .44704,
            "velocity_mps": [0, 0, 0], "control": {},
            "gate_indication": gate["indication"]})
    files["trace.jsonl"] = "".join(compact(row) + "\n" for row in traces)
    files["capture/evidence.jsonl"] = "".join(compact(row) + "\n" for row in capture)
    files["capture/native/frames.jsonl"] = "".join(compact(row) + "\n" for row in native)
    files["capture/recorder_info.txt"] = "Create 1: vehicle.synthetic.cpu (0) at (-10,0,0)\nSynthetic CPU diagnostic; no CARLA recorder\n"
    files["capture/manifest.json"] = compact({"extraction_confirmed": True,
        "frames": 600, "acquisition": "synthetic_cpu_fixture",
        "observation_contract_version": 2, "required_observations": [],
        "sources": {"road.xodr": sha(files["road.xodr"]),
                    "trace.jsonl": sha(files["trace.jsonl"])}}) + "\n"
    videos = [{"path": camera + ".mkv", "frames": 600,
        "width": 1920 if camera == "overview" else 1280,
        "height": 1080 if camera == "overview" else 720,
        "fps": 20, "color": color} for camera, color in zip(
            CAMERAS, ("blue", "green", "white", "red"))]
    path = HERE / ("diagnostic-" + suffix + ".json")
    path.write_text(compact({"files": files, "graphs": graphs, "videos": videos}) + "\n")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Rail diagnostic exceeds 2 MiB: " + suffix)
    rel = str(path.relative_to(ROOT))
    recipe = {"format": "worker-fixture-recipe",
        "sources": [{"path": "diagnostic-input.json", "source": rel,
                     "sha256": sha(path.read_text())}],
        "generator": {"source": rel, "sha256": sha(path.read_text())}}
    (HERE / ("diagnostic-" + suffix + "-recipe.json")).write_text(
        json.dumps(recipe, indent=2) + "\n")
    return {"case": suffix, "bytes": path.stat().st_size, "sha256": sha(path.read_text())}


if __name__ == "__main__":
    print(json.dumps([build("probe_" + letter) for letter in "abcde"], indent=2))
