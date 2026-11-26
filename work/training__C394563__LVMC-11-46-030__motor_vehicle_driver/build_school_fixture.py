"""Build source-shaped diagnostic inputs for one exact school-warning case.

All generated videos and intermediate files stay under .runtime-work. Fixture
source labels and black pixels do not establish original Native or legal facts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from prove_school_warning import trace
from school_warning_scene import open_drive


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
REVIEW_NAMES = ("school_lane_source", "child_identity_source",
                "warning_asset_source", "municipal_jurisdiction_source")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(rows):
    return "".join(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n"
                   for row in rows)


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def body(x, y, z=1):
    return [[x + dx, y + dy, zz] for dx in (-2, 2)
            for dy in (-1, 1) for zz in (z - .8, z + .8)]


def build(suffix):
    if suffix not in ("probe_1", "probe_2"):
        raise ValueError("Unknown exact school-warning case")
    case_id = ROOT.name + "__" + suffix
    temp = REPO / ".runtime-work" / ("c394563-fixture-build-" + suffix)
    if temp.exists():
        shutil.rmtree(temp)
    temp.mkdir(parents=True)
    dest = ROOT / "diagnostic" / suffix
    target_ft = 55 if suffix == "probe_1" else 40
    rows = trace(target_ft, release="signal_removed")
    frame_map, traces, evidence, native_frames, graphs = [], [], [], [], []
    for index, row in enumerate(rows):
        frame = row["native_frame"]
        t = (index + 1) / 20
        x, speed = row["vehicle_center_x_m"], row["observed_speed_mps"]
        row.update(vehicle_actor_id=12, warning_actor_id=13, child_actor_id=14,
                   vehicle_center_y_m=-1.75, vehicle_length_m=4.0,
                   warning_xyz_m=[-1, -6, 1 if index < 250 else -20],
                   child_xyz_m=[-2, -8, .5],
                   camera_native_frames={name: frame for name in CAMERAS},
                   original_lane_and_child_review_pending=True)
        frame_map.append({"video_frame": index, "native_frame": frame,
                          "carla_frame": frame, "time_s": t,
                          "camera_native_frames": row["camera_native_frames"]})
        xyz = [x, -1.75, 1]
        traces.append({"frame": frame, "time_s": t,
                       "position": {"x": x, "y": -1.75, "z": 1},
                       "position_m": xyz, "speed_mps": speed,
                       "speed_mph": speed * 2.2369362921,
                       "velocity_mps": [speed, 0, 0],
                       "heading_deg": 0.0, "control": {"diagnostic": True}})
        evidence.append({"original_frame": frame, "recording_time_s": t,
                         "actor_id": 12, "replay_frame": frame,
                         "replay_simulation_time_s": t,
                         "ego": {"position_m": xyz, "speed_mps": speed,
                                 "body_vertices_m": body(x, -1.75),
                                 "heading_deg": 0.0,
                                 "speed_provenance": "synthetic_native_sample",
                                 "synthetic_diagnostic": True},
                         "other_actors": [{"actor_id": 14, "sem_class": "pedestrian",
                                           "body_vertices_m": body(-2, -8)}],
                         "world": {"road_projection": {"road_id": 394563,
                                                       "section_id": 0, "lane_id": -1,
                                                       "s_m": x + 100},
                                   "weather": {"cloudiness": 0, "fog_density": 0,
                                               "precipitation": 0, "wetness": 0}}})
        name = str(index).zfill(8) + ".adapter.json"
        native_frames.append({"frame": frame, "time_s": t,
                              "simulation_time": t,
                              "base": "graphs/base/" + name,
                              "adapter_graph": "graphs/base/" + name,
                              "nodes": 2, "edges": 0})
        graphs.append({"path": "capture/native/graphs/base/" + name,
                       "attributes": {"frame": frame,
                                      "simulation_time_s": t,
                                      "source": "C394563 generated CPU diagnostic",
                                      "synthetic_diagnostic": True},
                       "edges": [], "nodes": [
                           {"id": "ego", "attributes": {
                               "entity_id": 12, "sem_class": "ego",
                               "vertex": xyz, "forward": [1, 0, 0],
                               "threedbbox": body(x, -1.75)}},
                           {"id": "child", "attributes": {
                               "entity_id": 14, "sem_class": "pedestrian",
                               "vertex": [-2, -8, .5], "forward": [0, 1, 0],
                               "threedbbox": body(-2, -8)}}]})
    write(temp / "native-rows.jsonl", lines(rows))
    write(temp / "video_frames.jsonl", lines(frame_map))
    write(temp / "trace.jsonl", lines(traces))
    write(temp / "capture/evidence.jsonl", lines(evidence))
    write(temp / "road.xodr", open_drive() + "\n")
    review = {"school_pedestrian_lane_survey": True,
              "municipal_jurisdiction_reviewed": True,
              "nearest_lane_side_x_m": 0.0,
              "lane_marker_blueprint": "static.prop.school_lane",
              "warning_blueprint": "static.prop.warning",
              "child_blueprint": "walker.pedestrian.0001",
              "synthetic_diagnostic": True}
    for name in REVIEW_NAMES:
        path = temp / ("review-" + name)
        write(path, name + " synthetic source-shaped diagnostic\n")
        review[name + "_sha256"] = sha(path)
    write(temp / "original-school-lane-review.json", json.dumps(review) + "\n")
    videos = []
    for index, name in enumerate(CAMERAS):
        width, height = (1920, 1080) if index == 0 else (1280, 720)
        videos.append({"path": name + ".mkv", "frames": 600,
                       "width": width, "height": height, "fps": 20, "color": "black"})
        subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                        "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r=20",
                        "-frames:v", "600", "-an", "-c:v", "ffv1", "-threads", "1",
                        "-fflags", "+bitexact", "-flags:v", "+bitexact",
                        str(temp / (name + ".mkv"))], check=True, timeout=120)
    sealed = ["road.xodr", "native-rows.jsonl", "video_frames.jsonl",
              "original-school-lane-review.json"] + ["review-" + name for name in REVIEW_NAMES]
    sealed += [name + ".mkv" for name in CAMERAS]
    write(temp / "captured-source-hashes.json", json.dumps({
        "source_kind": "original_native_capture", "case_id": case_id,
        "sha256": {name: sha(temp / name) for name in sealed},
        "synthetic_diagnostic": True}) + "\n")
    write(temp / "capture/manifest.json", json.dumps({
        "extraction_confirmed": True, "frames": 600,
        "synthetic_diagnostic": True,
        "sources": {name: sha(temp / name) for name in
                    ("road.xodr", "native-rows.jsonl", "trace.jsonl")}}) + "\n")
    write(temp / "capture/recorder_info.txt",
          "Synthetic diagnostic; no Native recording.\nCreate 12: vehicle.tesla.model3 (0)\n")
    sources = []
    for name in sealed[:8] + ["captured-source-hashes.json", "trace.jsonl",
                              "capture/evidence.jsonl", "capture/manifest.json"]:
        path = dest / "sources" / name
        write(path, (temp / name).read_text())
        sources.append({"path": name, "source": str(path.relative_to(REPO)),
                        "sha256": sha(path)})
    spec = {"files": {"capture/native/frames.jsonl": lines(native_frames),
                       "capture/recorder_info.txt":
                           (temp / "capture/recorder_info.txt").read_text()},
            "graphs": graphs, "videos": videos}
    spec_path = dest / "fixture-spec.json"
    write(spec_path, json.dumps(spec, separators=(",", ":")) + "\n")
    recipe = {"format": "worker-fixture-recipe",
              "generator": {"source": str(spec_path.relative_to(REPO)),
                            "sha256": sha(spec_path)}, "sources": sources}
    recipe_path = dest / "fixture-recipe.json"
    write(recipe_path, json.dumps(recipe, indent=2) + "\n")
    return {"case_id": case_id, "recipe_sha256": sha(recipe_path),
            "source_count": len(sources), "graph_count": len(graphs)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("suffix", choices=("probe_1", "probe_2"))
    args = parser.parse_args()
    print(json.dumps(build(args.suffix)))
