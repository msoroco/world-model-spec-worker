"""Build a source-bound synthetic adapter fixture for one 800-frame draft case."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = HERE / "current-v2-fixture"
sys.path.insert(0, str(HERE / "native"))
from geometry import open_drive


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n" for row in rows))


def main():
    samples = read_rows(SOURCE / "native_samples.jsonl")
    trace = read_rows(SOURCE / "trace.jsonl")
    evidence = read_rows(SOURCE / "capture/evidence.jsonl")
    if len(samples) != len(trace) or len(trace) != len(evidence) or len(samples) != 800:
        raise ValueError("Exact 800-frame synthetic source required")
    graph_items = []
    frame_rows = []
    for sample, movement, event in zip(samples, trace, evidence):
        frame = sample["native_frame"]
        time = sample["time_s"]
        x, y = sample["native_center_xy_m"]
        movement.update(position_m=[x, y, .5], speed_mph=sample["speed_mps"] / .44704,
                        control={"throttle": 0, "brake": 0, "hand_brake": False})
        event.update(replay_frame=frame, replay_simulation_time_s=time, actor_id=107)
        event["ego"].update(position_m=[x, y, .5], heading_deg=sample["heading_deg"],
                            speed_mps=sample["speed_mps"],
                            speed_provenance="synthetic_native_sample",
                            synthetic_diagnostic=True)
        event["world"] = {"weather": {"cloudiness": 0, "precipitation": 0,
                                         "wetness": 0, "fog_density": 0},
                          "road_projection": {"road_id": 1, "section_id": 0,
                                              "lane_id": -1, "s_m": x + 120}}
        relative = f"graphs/base/{frame:08d}.adapter.json"
        graph_items.append({"path": "capture/native/" + relative,
                            "attributes": {"frame": frame, "simulation_time_s": time,
                                           "synthetic_diagnostic": True,
                                           "source": "C329610 source-bound signal CPU fixture"},
                            "nodes": [{"id": "ego", "attributes": {
                                "sem_class": "ego", "entity_id": 107,
                                "vertex": [x, y, .5],
                                "forward": sample["native_forward_xy"] + [0.0],
                                "threedbbox": event["ego"]["body_vertices_m"]}}],
                            "edges": []})
        frame_rows.append({"frame": frame, "simulation_time": time,
                           "adapter_graph": relative, "base": relative,
                           "nodes": 1, "edges": 0})
    write_rows(SOURCE / "trace.jsonl", trace)
    write_rows(SOURCE / "capture/evidence.jsonl", evidence)
    road = SOURCE / "road.xodr"
    road.write_text(open_drive())
    manifest = json.loads((SOURCE / "capture/manifest.json").read_text())
    manifest.update(synthetic_diagnostic=True,
                    sources={"road.xodr": sha(road), "trace.jsonl": sha(SOURCE / "trace.jsonl")})
    (SOURCE / "capture/manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    specification = HERE / "current-v2-fixture-spec.json"
    spec = json.loads(specification.read_text())
    spec["files"] = {"capture/native/frames.jsonl": "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in frame_rows),
                     "capture/recorder_info.txt": "Create 107: vehicle.lincoln.mkz_2020\n"}
    spec["graphs"] = graph_items
    specification.write_text(json.dumps(spec, separators=(",", ":"), allow_nan=False) + "\n")
    recipe_path = HERE / "current-v2-fixture-recipe.json"
    recipe = json.loads(recipe_path.read_text())
    recipe["sources"] = [{"path": path, "source": str((SOURCE / path).relative_to(ROOT)),
                          "sha256": sha(SOURCE / path)}
                         for path in ("road_geometry.json", "trace.jsonl", "video_frames.jsonl",
                                      "native_samples.jsonl", "body_history.jsonl", "road.xodr",
                                      "capture/evidence.jsonl", "capture/manifest.json")]
    recipe["generator"]["sha256"] = sha(specification)
    recipe_path.write_text(json.dumps(recipe, indent=2) + "\n")
    print(json.dumps({"spec_sha256": sha(specification), "recipe_sha256": sha(recipe_path),
                      "graphs": len(graph_items), "spec_bytes": specification.stat().st_size}))


if __name__ == "__main__":
    main()
