"""Build source-shaped CPU diagnostics; these are never physical recordings."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE / "native/tests"))
from test_saved import fixture

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def compact(value):
    return json.dumps(value, separators=(",", ":"), allow_nan=False)


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def build(number):
    tag = f"probe_0{number}"
    with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work", prefix="c178965-source-") as temporary:
        path = Path(temporary) / tag
        path.mkdir()
        fixture(path, number)
        files = {str(file.relative_to(path)): file.read_text() for file in path.rglob("*") if file.is_file()}
    bodies = [json.loads(line) for line in files["roadside-native.jsonl"].splitlines()]
    maps = [json.loads(line) for line in files["video_frames.jsonl"].splitlines()]
    capture, native, graphs, traces = [], [], [], []
    for body, mapping in zip(bodies, maps):
        i, t, frame = mapping["video_frame"], mapping["time_s"], mapping["native_frame"]
        participants = []
        for actor_id, label, y in ((1, "ego", body["y_m"]), (2, "other", -2.0)):
            x = 10 if actor_id == 1 else -8
            vertices = ([[xx, yy, z] for xx in (x - 2.25, x + 2.25)
                         for yy in (y - .9, y + .9) for z in (-.7, .7)]
                        if actor_id == 1 else [[x - 2.25, y - .9, 0], [x + 2.25, y + .9, 0]])
            participants.append({"actor_id": actor_id, "blueprint": "vehicle.synthetic.cpu",
                                 "body_vertices_m": vertices, "heading_deg": 0,
                                 "velocity_mps": [0, 0, 0],
                                 "speed_mps": body["speed_mps"] if actor_id == 1 else 0.0,
                                 "accel_longitudinal_mps2": 0.0})
        observed = {"frame": frame, "time_s": t, "participants": participants,
                    "world_settings": {"no_rendering_mode": False},
                    "rgb_sensors": {view: {"frame": i} for view in CAMERAS}}
        graph_path = f"graphs/base/{i:08d}.adapter.json"
        graphs.append({"path": "capture/native/" + graph_path,
                       "attributes": {"frame": i, "observed_evidence": observed},
                       "nodes": [], "edges": []})
        native.append({"frame": i, "time_s": t, "simulation_time": t,
                       "base": graph_path, "adapter_graph": graph_path})
        capture.append({"original_frame": frame, "replay_frame": i, "actor_id": 1,
                        "recording_time_s": t, "replay_simulation_time_s": t,
                        "ego": {"position_m": [10, body["y_m"], 0], "heading_deg": 0,
                                "speed_mps": body["speed_mps"],
                                "speed_provenance": "synthetic_native_sample",
                                "body_vertices_m": participants[0]["body_vertices_m"]},
                        "world": {"weather": {"cloudiness": 0, "precipitation": 0,
                                              "wetness": 0, "fog_density": 0},
                                  "road_projection": {"road_id": 1, "section_id": 0,
                                                      "lane_id": -1, "s_m": i / 20}},
                        "original_observations": observed})
        traces.append({"frame": frame, "time_s": t,
                       "position": {"x": 10, "y": body["y_m"], "z": 0},
                       "position_m": [10, body["y_m"], 0], "heading_deg": 0,
                       "speed_mps": body["speed_mps"],
                       "speed_mph": body["speed_mps"] / .44704,
                       "velocity_mps": [0, 0, 0], "control": {}})
    files["trace.jsonl"] = "".join(compact(row) + "\n" for row in traces)
    files["capture/evidence.jsonl"] = "".join(compact(row) + "\n" for row in capture)
    files["capture/native/frames.jsonl"] = "".join(compact(row) + "\n" for row in native)
    files["capture/recorder_info.txt"] = "Create 1: vehicle.synthetic.cpu (0) at (10,0,0)\nSynthetic CPU diagnostic; no CARLA recorder\n"
    original = json.loads((REPO / "runtime/fixtures/example.json").read_text())
    files["road.xodr"] = original["files"]["road.xodr"]
    files["capture/manifest.json"] = compact({
        "extraction_confirmed": True, "frames": 600,
        "acquisition": "synthetic_cpu_fixture", "observation_contract_version": 2,
        "required_observations": [],
        "sources": {"road.xodr": sha(files["road.xodr"]),
                    "trace.jsonl": sha(files["trace.jsonl"])}}) + "\n"
    videos = [{"path": view + ".mkv", "frames": 600,
               "width": 1920 if view == "overview" else 1280,
               "height": 1080 if view == "overview" else 720,
               "fps": 20, "color": color} for view, color in zip(
                   CAMERAS, ("blue", "green", "white", "red"))]
    source = HERE / f"diagnostic-{tag}.json"
    source.write_text(compact({"files": files, "graphs": graphs, "videos": videos}) + "\n")
    if source.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Diagnostic exceeds 2 MiB: " + tag)
    relative = str(source.relative_to(REPO))
    recipe = {"format": "worker-fixture-recipe",
              "sources": [{"path": "diagnostic-input.json", "source": relative,
                           "sha256": sha(source.read_text())}],
              "generator": {"source": relative, "sha256": sha(source.read_text())}}
    (HERE / f"diagnostic-{tag}-recipe.json").write_text(json.dumps(recipe, indent=2) + "\n")
    return {"case": tag, "bytes": source.stat().st_size, "sha256": sha(source.read_text())}


if __name__ == "__main__":
    print(json.dumps([build(i) for i in (1, 2, 3)], indent=2))
