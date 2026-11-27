"""Build textual, source-hashed CPU fixtures for the exact U-turn requests.

These samples are synthetic software diagnostics, never Native observations.
"""

import hashlib
import json
from pathlib import Path

from road_request import CAMERAS, request


ROOT = Path(__file__).resolve().parents[1]


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip("\n") + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def square(x, y):
    return [[x - .1, y - .1], [x + .1, y - .1],
            [x + .1, y + .1], [x - .1, y + .1]]


def build(case):
    q = request(case)
    directory = ROOT / "diagnostic" / case
    directory.mkdir(parents=True, exist_ok=True)
    authority = directory / "authority-source.json"
    write(authority, encode({"public_authority_establishment": "unassessed",
                             "diagnostic_only": True}))
    write(directory / "authority-review.json", encode({
        "format": "worker-divided-road-authority-source",
        "source": {"path": authority.name, "sha256": sha(authority)}}))
    write(directory / "divided-road-context.json", encode({
        "source_kind": "synthetic_native_sample",
        "median_bounds_m": q["median_bounds_m"],
        "opening_bounds_m": q["opening_bounds_m"],
        "barrier_bounds_m": q["barrier_bounds_m"],
        "authored_road_ids": q["road_ids"],
        "native_roadways": [{"road_id": road_id, "lane_id": -1,
                             "heading_deg": heading, "center_y_m": center,
                             "lane_width_m": 3.5}
                            for road_id, heading, center in zip(
                                q["road_ids"], (0, 180), (-6.75, 6.75))]}))
    cameras = [name for name, _, _ in CAMERAS]
    crossing_x = q["requested_crossing_x_m"]
    native, mapping, trace, body, evidence, frames, graphs = [], [], [], [], [], [], []
    for index in range(600):
        frame, time_s = index + 30, index / 20
        y = -6.75 + 13.5 * index / 599
        xy = square(crossing_x, y)
        xyz = [crossing_x, y, 1]
        vertices = [[x, yy, z] for x, yy in xy for z in (0, 1.8)]
        native.append({"native_frame": frame, "video_frame": index,
                       "time_s": time_s, "ego": {"actor_id": 1,
                       "blueprint_id": "vehicle.tesla.model3", "body_xy_m": xy,
                       "yaw_deg": 90}})
        mapping.append({"native_frame": frame, "carla_frame": frame,
                        "video_frame": index, "time_s": time_s,
                        "camera_native_frames": {name: frame for name in cameras}})
        trace.append({"frame": frame, "time_s": time_s,
                      "position": {"x": xyz[0], "y": xyz[1], "z": xyz[2]},
                      "position_m": xyz, "heading_deg": 90, "speed_mps": 0.45,
                      "speed_mph": 0.45 / .44704,
                      "velocity_mps": [0, 0.45, 0],
                      "control": {"diagnostic": True}})
        body.append({"frame": frame, "time_s": time_s,
                     "position_m": xyz, "heading_deg": 90,
                     "body_vertices_m": vertices})
        evidence.append({"actor_id": 1, "original_frame": frame,
                         "replay_frame": frame, "recording_time_s": time_s,
                         "replay_simulation_time_s": time_s,
                         "ego": {"position_m": xyz, "heading_deg": 90,
                                 "speed_mps": 0.45,
                                 "speed_provenance": "synthetic_native_sample",
                                 "body_vertices_m": vertices,
                                 "synthetic_diagnostic": True},
                         "other_actors": [], "world": {"road_projection": {
                             "road_id": q["road_ids"][0] if y < 0 else q["road_ids"][1],
                             "lane_id": -1, "section_id": 0, "s_m": index / 20}}})
        graph_path = f"capture/native/graphs/base/{index:08d}.adapter.json"
        frames.append({"frame": frame, "simulation_time": time_s,
                       "base": f"graphs/base/{index:08d}.adapter.json",
                       "adapter_graph": f"graphs/base/{index:08d}.adapter.json",
                       "nodes": 1, "edges": 0})
        graphs.append({"path": graph_path,
                       "attributes": {"frame": frame, "simulation_time_s": time_s,
                                      "synthetic_diagnostic": True},
                       "nodes": [{"id": "ego", "attributes": {
                           "entity_id": 1, "sem_class": "ego", "vertex": xyz,
                           "forward": [0, 1, 0], "threedbbox": vertices}}],
                       "edges": []})
    sources = {"divided-road-context.json": directory / "divided-road-context.json",
               "authority-review.json": directory / "authority-review.json",
               "authority-source.json": authority}
    for name, rows in (("native-uturn.jsonl", native),
                       ("video_frames.jsonl", mapping),
                       ("trace.jsonl", trace),
                       ("body_history.jsonl", body),
                       ("capture/evidence.jsonl", evidence)):
        path = directory / name
        write(path, "\n".join(encode(row) for row in rows))
        sources[name] = path
    write(directory / "capture-manifest.json", encode({
        "extraction_confirmed": True, "frames": 600,
        "synthetic_diagnostic": True,
        "sources": {"road.xodr": hashlib.sha256(q["source_map"].encode()).hexdigest(),
                    "trace.jsonl": sha(sources["trace.jsonl"])}}))
    sources["capture/manifest.json"] = directory / "capture-manifest.json"
    write(directory / "recorder_info.txt",
          "Synthetic diagnostic; no Native recording.\n"
          "Create 1: vehicle.tesla.model3 (0)")
    sources["capture/recorder_info.txt"] = directory / "recorder_info.txt"
    specification = {"files": {"capture/native/frames.jsonl": "\n".join(
        encode(row) for row in frames) + "\n"}, "graphs": graphs,
        "videos": [{"path": name + ".mkv", "frames": 600, "width": width,
                    "height": height, "fps": 20, "color": "black"}
                   for name, width, height in CAMERAS]}
    spec_path = directory / "fixture-spec.json"
    write(spec_path, encode(specification))
    repo = ROOT.parents[1]
    recipe = {"format": "worker-fixture-recipe",
              "generator": {"source": str(spec_path.relative_to(repo)),
                            "sha256": sha(spec_path)},
              "sources": [{"path": name, "source": str(path.relative_to(repo)),
                           "sha256": sha(path)}
                          for name, path in sorted(sources.items())]}
    write(directory / "fixture-recipe.json", encode(recipe))
    return directory / "fixture-recipe.json"


if __name__ == "__main__":
    for case_name in ("authorized_opening", "barrier_crossing"):
        print(build(case_name))
