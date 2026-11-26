"""Generate source-hashed, textual 600-frame diagnostics for exact cases.

The review rows are synthetic software inputs. They deliberately leave actual
driver observation unknown and cannot qualify legal or physical success.
"""

import hashlib
import json
from pathlib import Path

from branch_meter import BRANCH_SOURCES
from prove_branch_constructions import synthetic_survey
from prove_branch_meter import packet as synthetic_packet


ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(items):
    return "".join(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n"
                   for row in items)


def build(suffix):
    config = json.loads((ROOT / "cases" / suffix / "config.json").read_text())
    branch = config["branch"]
    folder = ROOT / "selected-source" / suffix
    folder.mkdir(parents=True, exist_ok=True)
    survey = synthetic_survey(branch, BRANCH_SOURCES[branch])
    survey["case_id"] = config["case_id"]
    survey["diagnostic_fixture"] = True
    survey_path = folder / "context-survey.json"
    survey_path.write_text(json.dumps(survey, indent=2) + "\n")
    survey_hash = sha(survey_path)
    sample = synthetic_packet(branch)["trace"]
    capture, review, core, evidence, frame_map, frames, graphs = [], [], [], [], [], [], []
    for row in sample:
        index = row["frame"]
        native = 2000 + index
        time_s = index / 20
        x, y, px, py = row["ego_x_m"], row["ego_y_m"], row["ped_x_m"], row["ped_y_m"]
        speed = row["ego_speed_mps"]
        capture.append({"source_kind": "synthetic_capture_fixture", "branch": branch,
            "frame": index, "video_frame": index, "native_frame": native,
            "time_s": time_s, "context_survey_sha256": survey_hash,
            "ego_actor_id": 101, "pedestrian_actor_id": 102,
            "ego_x_m": x, "ego_y_m": y, "ped_x_m": px, "ped_y_m": py,
            "ego_speed_mps": speed, "driver_observed_pedestrian": None,
            "driver_observation_source": None,
            "line_of_sight_clear": None, "branch_position_evidenced": None,
            "requested_control": {"phase": "slow_request" if config["mode"] == "caution" and index >= 150 else "approach_request"}})
        review.append({"source_kind": "original_saved_source_review",
            "frame": index, "native_frame": native, "video_frame": index,
            "context_survey_sha256": survey_hash,
            "line_of_sight_clear": index >= 50,
            "branch_position_evidenced": index >= 30,
            "driver_observed_pedestrian": None,
            "driver_observation_source": None})
        core.append({"frame": native, "time_s": time_s,
            "position": {"x": x, "y": y, "z": 1.0},
            "position_m": [x, y, 1.0], "heading_deg": 0.0,
            "speed_mps": speed, "speed_mph": speed / .44704,
            "control": {"throttle": 0.2, "brake": 0.0, "hand_brake": False},
            "synthetic_diagnostic": True, "velocity_mps": [speed, 0, 0],
            "speed_provenance": "synthetic_native_sample"})
        body = [[x + dx, y + dy, z] for dx, dy in
                ((-2, -1), (2, -1), (2, 1), (-2, 1)) for z in (0, 1.5)]
        evidence.append({"original_frame": native, "replay_frame": native,
            "actor_id": 101, "recording_time_s": time_s,
            "replay_simulation_time_s": time_s,
            "ego": {"position_m": [x, y, 1.0], "heading_deg": 0,
                    "speed_mps": speed, "speed_provenance": "synthetic_native_sample",
                    "body_vertices_m": body},
            "world": {"weather": {"cloudiness": 0, "precipitation": 0,
                                  "wetness": 0, "fog_density": 0},
                      "road_projection": {"road_id": 1, "section_id": 0,
                                          "lane_id": -1, "s_m": max(0, x + 100)}}})
        frame_map.append({"video_frame": index, "carla_frame": native,
            "native_frame": native, "time_s": time_s,
            "camera_native_frames": {name: native for name in CAMERAS}})
        graph_name = f"{native:08d}.adapter.json"
        frames.append({"frame": native, "time_s": time_s,
            "simulation_time": time_s, "synthetic_diagnostic": True,
            "adapter_graph": "graphs/base/" + graph_name})
        graphs.append({"path": "capture/native/graphs/base/" + graph_name,
                       "attributes": {"frame": native}, "nodes": [], "edges": []})
    files = {"pedestrian-caution-trace.jsonl": rows(capture),
             "pedestrian-source-review.jsonl": rows(review),
             "trace.jsonl": rows(core),
             "capture/evidence.jsonl": rows(evidence),
             "capture/native/frames.jsonl": rows(frames),
             "video_frames.jsonl": rows(frame_map),
             "capture/recorder_info.txt": "Create 101: vehicle.tesla.model3\nCreate 102: walker.pedestrian.0001\n",
             "acquisition-provenance.json": json.dumps({
                 "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
                 "native_executed": False}) + "\n"}
    files["road.xodr"] = json.loads((REPO / "runtime" / "fixtures" / "example.json").read_text())["files"]["road.xodr"]
    files["capture/manifest.json"] = json.dumps({
        "extraction_confirmed": True, "frames": 600,
        "required_observations": config["required_atoms"],
        "synthetic_diagnostic": True,
        "sources": {"trace.jsonl": hashlib.sha256(files["trace.jsonl"].encode()).hexdigest(),
                    "context-survey.json": survey_hash,
                    "road.xodr": hashlib.sha256(files["road.xodr"].encode()).hexdigest()}}, indent=2) + "\n"
    videos = [{"path": name + ".mkv", "frames": 600,
        "width": 1920 if name == "overview" else 1280,
        "height": 1080 if name == "overview" else 720,
        "fps": 20, "color": color} for name, color in
        zip(CAMERAS, ("blue", "green", "white", "red"))]
    generator = {"files": files, "graphs": graphs, "videos": videos}
    generator_path = ROOT / ("selected-generator-" + suffix + ".json")
    generator_path.write_text(json.dumps(generator, separators=(",", ":")) + "\n")
    recipe = {"format": "worker-fixture-recipe", "sources": [{
        "path": "context-survey.json",
        "source": str(survey_path.relative_to(REPO)), "sha256": sha(survey_path)}],
        "generator": {"source": str(generator_path.relative_to(REPO)),
                      "sha256": sha(generator_path)}}
    recipe_path = ROOT / ("selected-recipe-" + suffix + ".json")
    recipe_path.write_text(json.dumps(recipe, indent=2) + "\n")
    return {"case_id": config["case_id"], "generator_sha256": sha(generator_path),
            "recipe_sha256": sha(recipe_path), "generator_bytes": generator_path.stat().st_size}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", action="append")
    args = parser.parse_args()
    suffixes = args.case or [entry["case_id"].rsplit("__", 1)[-1] for entry in
                            json.loads((ROOT / "selected-contract-index.json").read_text())["cases"]]
    print(json.dumps([build(suffix) for suffix in suffixes]))
