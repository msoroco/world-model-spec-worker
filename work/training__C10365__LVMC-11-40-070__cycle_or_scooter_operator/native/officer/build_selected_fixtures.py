"""Build a retained, synthetic 600-frame source recipe for the current runtime.

This is a software diagnostic. It supplies no original Native motion, pixels,
Police Officer authority, or legal finding.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build import HERE
from prove_saved import fixture

ROOT = HERE.parents[3]
TARGET = HERE / "current-v2-primary-fixture"
SPEC = HERE / "current-v2-primary-fixture-spec.json"
RECIPE = HERE / "current-v2-primary-fixture-recipe.json"
BUNDLE = HERE / "drafts/probe_a/primary"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n"
                            for row in rows))


def build():
    TARGET.mkdir(parents=True, exist_ok=True)
    raw_path, video_path, review_path = fixture(BUNDLE, TARGET)
    raw = [json.loads(line) for line in raw_path.read_text().splitlines()]
    video = [json.loads(line) for line in video_path.read_text().splitlines()]
    assert len(raw) == len(video) == 600
    trace, evidence, native_frames, graphs = [], [], [], []
    for row, mapped in zip(raw, video):
        frame = row["native_frame"]
        time = row["time_s"]
        rider = row["rider"]
        officer = row["officer_actor"]
        x, y, z = rider["center_native_xyz_m"]
        body = rider["body_native_xyz_m"]
        trace.append({"frame": frame, "time_s": time,
                      "position": {"x": x, "y": y, "z": z},
                      "position_m": [x, y, z], "heading_deg": 0,
                      "speed_mps": rider["speed_mps"],
                      "velocity_mps": [rider["speed_mps"], 0, 0],
                      "speed_mph": rider["speed_mps"] * 2.2369362921,
                      "control": {"throttle": 0, "brake": 0,
                                  "hand_brake": False}})
        evidence.append({
            "original_frame": frame, "recording_time_s": time,
            "ego": {"body_vertices_m": body, "position_m": [x, y, z],
                    "heading_deg": 0, "speed_mps": rider["speed_mps"],
                    "speed_provenance": "synthetic_native_sample",
                    "synthetic_diagnostic": True},
            "replay_frame": frame, "replay_simulation_time_s": time,
            "actor_id": rider["actor_id"],
            "world": {"weather": {"cloudiness": 0, "precipitation": 0,
                                 "wetness": 0, "fog_density": 0},
                      "road_projection": {"road_id": 365, "section_id": 0,
                                          "lane_id": -1, "s_m": x}}})
        graph_path = f"capture/native/graphs/base/{frame:08d}.adapter.json"
        native_frames.append({"frame": frame, "simulation_time": time,
                              "adapter_graph": f"graphs/base/{frame:08d}.adapter.json",
                              "base": f"graphs/base/{frame:08d}.adapter.json",
                              "nodes": 2, "edges": 0})
        graphs.append({"path": graph_path,
                       "attributes": {"frame": frame,
                                      "simulation_time_s": time,
                                      "synthetic_diagnostic": True,
                                      "source": "C10365 source-bound rider/officer CPU fixture"},
                       "nodes": [
                           {"id": "ego", "attributes": {
                               "sem_class": "ego", "entity_id": rider["actor_id"],
                               "vertex": [x, y, z], "forward": [1, 0, 0],
                               "threedbbox": body}},
                           {"id": "officer", "attributes": {
                               "sem_class": "person", "entity_id": officer["actor_id"],
                               "vertex": officer["center_native_xyz_m"],
                               "forward": [1, 0, 0],
                               "threedbbox": officer["body_native_xyz_m"]}}],
                       "edges": []})
    write_rows(TARGET / "trace.jsonl", trace)
    write_rows(TARGET / "capture/evidence.jsonl", evidence)
    write_rows(TARGET / "video_frames.jsonl", [
        {"video_frame": row["video_frame"], "native_frame": row["native_frame"],
         "carla_frame": row["native_frame"], "time_s": row["time_s"]}
        for row in video])
    road = BUNDLE / "alley-stop.xodr"
    (TARGET / "road.xodr").write_bytes(road.read_bytes())
    write_json(TARGET / "capture/manifest.json", {
        "extraction_confirmed": True, "frames": 600,
        "synthetic_diagnostic": True,
        "sources": {"road.xodr": sha(TARGET / "road.xodr"),
                    "trace.jsonl": sha(TARGET / "trace.jsonl")}})
    write_json(SPEC, {
        "files": {"capture/native/frames.jsonl": "".join(
            json.dumps(row, separators=(",", ":")) + "\n" for row in native_frames),
                  "capture/recorder_info.txt":
                  "Create 17: vehicle.bh.crossbike (synthetic diagnostic)\n"
                  "Create 23: walker.pedestrian.0001 (synthetic diagnostic)\n"},
        "graphs": graphs,
        "videos": [{"path": name + ".mkv", "frames": 600,
                    "width": width, "height": height,
                    "fps": 20, "color": "black"}
                   for name, width, height in (
                       ("overview", 1920, 1080), ("approach", 1280, 720),
                       ("reference_corner", 1280, 720),
                       ("driver_reference", 1280, 720))]})
    sources = []
    for path in sorted(TARGET.rglob("*")):
        if path.is_file():
            relative = path.relative_to(TARGET).as_posix()
            sources.append({"path": relative,
                            "source": path.relative_to(ROOT).as_posix(),
                            "sha256": sha(path)})
    write_json(RECIPE, {"format": "worker-fixture-recipe", "sources": sources,
                        "generator": {"source": SPEC.relative_to(ROOT).as_posix(),
                                      "sha256": sha(SPEC)}})
    return {"sources": len(sources), "graphs": len(graphs),
            "spec_sha256": sha(SPEC), "recipe_sha256": sha(RECIPE)}


if __name__ == "__main__":
    for case in ("probe_a", "probe_b"):
        for candidate in ("primary", "fallback1", "fallback2"):
            name = case + "-" + candidate
            TARGET = HERE / "selected-fixtures" / name
            SPEC = HERE / "selected-specs" / (name + ".json")
            RECIPE = HERE / "selected-recipes" / (name + ".json")
            BUNDLE = HERE / "drafts" / case / candidate
            print(name, json.dumps(build(), sort_keys=True))
