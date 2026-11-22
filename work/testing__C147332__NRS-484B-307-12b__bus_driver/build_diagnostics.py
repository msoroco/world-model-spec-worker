"""Build four explicit original-shaped red-X software fixtures and recipes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from bus_route import ROUTES


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def dumps(value):
    return json.dumps(value, sort_keys=True, allow_nan=False) + "\n"


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def diagnostic(scene, kind):
    files, graphs = {}, []
    files["highway.txt"] = "Synthetic highway descriptor for software diagnostic only\n"
    files["device.txt"] = "Synthetic overhead red-X descriptor for software diagnostic only\n"
    files["original-capture.txt"] = "Synthetic original-shaped capture source\n"
    descriptor = lambda path: {"source_path": path, "source_sha256": digest(files[path]),
                               "reviewer": "software fixture", "source_citation": "diagnostic only"}
    packet = {"review_status": "reviewed",
              "highway": {**descriptor("highway.txt"), "status": "public_highway_reviewed"},
              "official_device": {**descriptor("device.txt"),
                  "device_kind": "official_overhead_lane_signal", "symbol": "red_x",
                  "faces_bus": True, "governed_lane_id": "red_lane",
                  "native_asset_blueprint_id": "fixture.red_x_asset"}}
    files["reviewed-context.json"] = dumps(packet)
    positions = {
        "adjacent_travel": [(10, -5.4), (20, -5.4), (30, -5.4), (40, -5.4), (55, -5.4)],
        "lateral_entry": [(10, -5.4), (20, -5.4), (30, -5.4), (40, -3.9), (55, -1.8)],
        "red_lane_stand": [(45, -1.8)] * 5,
        "red_lane_drive": [(10, -1.8), (20, -1.8), (30, -1.8), (40, -1.8), (55, -1.8)],
    }[kind]
    streams = {name: [] for name in (
        "video_frames.jsonl", "bus-body-history.jsonl", "lane-signal-history.jsonl",
        "camera-frame-map.jsonl", "sign-state-original.jsonl", "controller-history.jsonl",
        "trace.jsonl", "capture/evidence.jsonl", "capture/native/frames.jsonl")}
    camera_names = ["overview", "approach", "reference_corner", "driver_reference"]
    for index, (x, y) in enumerate(positions):
        time = round(index * .05, 4)
        common = {"frame": index, "elapsed_seconds": time}
        footprint = [[x - 5, y - 1], [x + 5, y - 1],
                     [x + 5, y + 1], [x - 5, y + 1]]
        streams["video_frames.jsonl"].append({"video_frame": index, "carla_frame": index,
                                               "time_s": time})
        streams["bus-body-history.jsonl"].append({**common,
            "source_path": "original-capture.txt", "bus_actor_id": 7,
            "bus_footprint": footprint})
        streams["lane-signal-history.jsonl"].append({**common,
            "source_path": "sign-state-original.jsonl", "governed_lane_id": "red_lane",
            "lane_lateral_bounds_m": [-3.6, 0.0], "symbol": "red_x", "faces_bus": True,
            "official_device_source_sha256": digest(files["device.txt"])})
        streams["camera-frame-map.jsonl"].append({**common,
            "source_path": "video_frames.jsonl", "camera_names": camera_names})
        streams["sign-state-original.jsonl"].append({**common,
            "head_actor_id": 8, "head_blueprint_id": "fixture.red_x_asset",
            "head_position": [50, -1.8, 6]})
        streams["controller-history.jsonl"].append({**common,
            "requested_control": {"throttle": 0 if kind == "red_lane_stand" else .3,
                                  "brake": 1 if kind == "red_lane_stand" else 0,
                                  "steer": 0}})
        streams["trace.jsonl"].append({"frame": index, "time_s": time,
            "position": {"x": x, "y": y, "z": 0}, "position_m": [x, y, 0],
            "heading_deg": 0, "speed_mps": 0 if kind == "red_lane_stand" else 8,
            "speed_mph": 0 if kind == "red_lane_stand" else 8 / .44704,
            "velocity_mps": [0 if kind == "red_lane_stand" else 8, 0, 0],
            "control": {}})
        observations = {"frame": index, "time_s": time, "participants": [],
                        "map_context": {"declared_public_way_road_ids": []}}
        streams["capture/evidence.jsonl"].append({"actor_id": 7,
            "ego": {"body_vertices_m": [[a, b, z] for a, b in footprint for z in (0, 2.5)],
                    "heading_deg": 0, "position_m": [x, y, 0],
                    "speed_mps": 0 if kind == "red_lane_stand" else 8,
                    "speed_provenance": "synthetic_native_sample"},
            "original_frame": index, "original_observations": observations,
            "recording_time_s": time, "replay_frame": index,
            "replay_simulation_time_s": time, "world": {"weather": {}}})
        graph_path = f"capture/native/graphs/base/{index:08d}.adapter.json"
        streams["capture/native/frames.jsonl"].append({
            "adapter_graph": graph_path.removeprefix("capture/native/"),
            "frame": index, "simulation_time": time})
        graphs.append({"path": graph_path, "attributes": {"frame": index,
                       "time_s": time, "observed_evidence": observations},
                       "nodes": [], "edges": []})
    for name, rows in streams.items():
        files[name] = "".join(dumps(row) for row in rows)
    files["acquisition-provenance.json"] = dumps({
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
        "scope": "software only; no physical or legal acceptance"})
    files["capture/recorder_info.txt"] = "Create 7: vehicle.mitsubishi.fusorosa (bus diagnostic) at (10, -5.4, 0)\n"
    files["capture/manifest.json"] = dumps({
        "acquisition": "original_live_run", "case_id": scene["case_id"],
        "complete_driving_lanes": False, "extraction_confirmed": True,
        "frames": len(positions), "sources": {
            "road.xodr": scene["map_source_sha256"],
            "trace.jsonl": digest(files["trace.jsonl"])}, "status": "draft"})
    files["acquisition.json"] = dumps({name: {"kind": "diagnostic_fixture",
        "sha256": digest(files[name])} for name in (
        "highway.txt", "device.txt", "original-capture.txt", "reviewed-context.json",
        "video_frames.jsonl", "bus-body-history.jsonl", "lane-signal-history.jsonl",
        "camera-frame-map.jsonl", "sign-state-original.jsonl", "controller-history.jsonl",
        "trace.jsonl")})
    videos = [{"path": name + ".mkv", "frames": len(positions), "width": width,
               "height": height, "fps": 20, "color": "black"}
              for name, width, height in (("overview", 1920, 1080),
                  ("approach", 1280, 720), ("reference_corner", 1280, 720),
                  ("driver_reference", 1280, 720))]
    return {"files": files, "graphs": graphs, "videos": videos}


def main():
    for kind in ROUTES:
        folder = ROOT / "cases" / kind
        scene = json.loads((folder / "scene.json").read_text())
        generator = folder / "diagnostic.json"
        generator.write_text(dumps(diagnostic(scene, kind)))
        note = folder / "diagnostic-source-note.json"
        note.write_text(dumps({"case_id": scene["case_id"],
            "scope": "synthetic original-shaped software diagnostic only"}))
        recipe = {"format": "worker-fixture-recipe", "sources": [{
            "path": "diagnostic-source-note.json",
            "source": str(note.relative_to(REPO)), "sha256": sha(note)}],
            "generator": {"source": str(generator.relative_to(REPO)),
                          "sha256": sha(generator)}}
        (folder / "fixture-recipe.json").write_text(json.dumps(recipe, indent=2) + "\n")
        print(kind, sha(generator))


if __name__ == "__main__":
    main()
