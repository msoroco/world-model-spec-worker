"""Author explicit synthetic source recipes for selected analysis CPU proofs."""
from __future__ import annotations

import hashlib
import json
import math
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "tests"))
from test_camera_sources import fixture


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> list:
    scratch = ROOT / ".runtime-work" / "c158208-owner-nov24b" / "tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    road_source = ROOT / "work/testing__C229439__NRS-484B-450-1o__motor_vehicle_driver/diagnostic-road.xodr"
    road_text = road_source.read_text()
    note = HERE / "fixture-source-note.json"
    note.write_text(json.dumps({"format": "c158208-synthetic-source-note-v1",
                                "scope": "three-frame software compatibility only",
                                "unrelated_diagnostic_road_source": {
                                    "path": str(road_source.relative_to(ROOT)),
                                    "sha256": _sha(road_source)},
                                "physical_acceptance": False}, indent=2) + "\n")
    built = []
    for kind in ("nearest_view_response", "nearest_view_uninterrupted"):
        case = HERE.name + "__" + kind
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            attempt = Path(directory) / "attempt"
            fixture(attempt)
            identity = json.loads((attempt / "capture-identity.json").read_text())
            identity["case_id"] = case
            (attempt / "capture-identity.json").write_text(json.dumps(identity, indent=2,
                                                                        sort_keys=True) + "\n")
            packet = json.loads((attempt / "nearest-view-saved-packet.json").read_text())
            originals = [json.loads(line) for line in
                         (attempt / "nearest-view-original-ticks.jsonl").read_text().splitlines()]
            traces = []
            mapping = []
            evidence = []
            native_frames = []
            graphs = []
            for index, (row, raw) in enumerate(zip(packet["samples"], originals)):
                vertices = raw["ego"]["body_vertices_xy_m"]
                velocity = raw["ego"]["velocity_xy_mps"]
                center = [sum(point[axis] for point in vertices) / len(vertices) for axis in (0, 1)]
                traces.append({"frame": row["frame"], "time_s": row["time_s"],
                               "position_m": [center[0], center[1], 0.0],
                               "position": {"x": center[0], "y": center[1], "z": 0.0},
                               "heading_deg": math.degrees(math.atan2(velocity[1], velocity[0])),
                               "speed_mps": row["ego_speed_mps"],
                               "speed_mph": row["ego_speed_mps"] / .44704,
                               "velocity_mps": [velocity[0], velocity[1], 0.0],
                               "control": {}})
                mapping.append({"video_frame": index, "carla_frame": row["frame"],
                                "native_frame": row["frame"],
                                "time_s": row["time_s"]})
                graph_name = f"graphs/base/{row['frame']:08d}.adapter.json"
                source_packet = {"frame": row["frame"], "time_s": row["time_s"],
                                 "participants": [],
                                 "map_context": {"diagnostic_fixture": True},
                                 "nearest_view_observation": {
                                     "visible": row["through_traffic_visible"],
                                     "through_vehicle_within_intersection":
                                         row["through_vehicle_within_intersection"]}}
                graphs.append({"path": "capture/native/" + graph_name,
                               "attributes": {"frame": row["frame"],
                                              "time_s": row["time_s"],
                                              "observed_evidence": source_packet},
                               "nodes": [], "edges": []})
                native_frames.append({"frame": row["frame"],
                                      "simulation_time": row["time_s"],
                                      "adapter_graph": graph_name})
                body = raw["ego"]["body_vertices_xy_m"]
                body_3d = [[point[0], point[1], z] for point in body for z in (0, 1)]
                evidence.append({"actor_id": 7, "original_frame": row["frame"],
                                 "replay_frame": row["frame"],
                                 "recording_time_s": row["time_s"],
                                 "replay_simulation_time_s": row["time_s"],
                                 "ego": {"body_vertices_m": body_3d,
                                         "position_m": traces[-1]["position_m"],
                                         "heading_deg": traces[-1]["heading_deg"],
                                         "speed_mps": row["ego_speed_mps"],
                                         "speed_provenance": "synthetic_native_sample"},
                                 "original_observations": source_packet,
                                 "world": {"weather": {}}})
            files = {name: (attempt / name).read_text() for name in (
                "capture-identity.json", "nearest-view-tick-seal.json",
                "nearest-view-original-ticks.jsonl", "nearest-view-saved-packet.json")}
            files["diagnostic-compatibility.json"] = json.dumps({
                "format": "c158208-generated-compatibility-v1", "case_id": case,
                "frame_count": 3, "source_kind": "synthetic_fixture"}, indent=2) + "\n"
            files["trace.jsonl"] = "".join(json.dumps(row) + "\n" for row in traces)
            files["video_frames.jsonl"] = "".join(json.dumps(row) + "\n" for row in mapping)
            files["road.xodr"] = road_text
            files["capture/evidence.jsonl"] = "".join(json.dumps(row) + "\n" for row in evidence)
            files["capture/native/frames.jsonl"] = "".join(json.dumps(row) + "\n" for row in native_frames)
            files["capture/recorder_info.txt"] = "Create 7: vehicle.tesla.model3 (diagnostic) at (0, 0, 0)\n"
            files["acquisition-provenance.json"] = json.dumps({
                "diagnostic_fixture": True, "provenance_kind": "synthetic_fixture"}) + "\n"
            files["capture/manifest.json"] = json.dumps({
                "acquisition": "synthetic_fixture", "diagnostic_fixture": True,
                "case_id": case, "extraction_confirmed": True,
                "frames": len(packet["samples"]),
                "sources": {"road.xodr": hashlib.sha256(road_text.encode()).hexdigest(),
                            "trace.jsonl": hashlib.sha256(files["trace.jsonl"].encode()).hexdigest()}}) + "\n"
            videos = [{"path": name + ".mkv", "frames": 3, "fps": 20,
                       "width": 1920 if name == "overview" else 1280,
                       "height": 1080 if name == "overview" else 720,
                       "color": color} for name, color in (
                ("overview", "white"), ("approach", "red"),
                ("reference_corner", "green"), ("driver_reference", "blue"))]
            spec_path = HERE / ("diagnostic-fixture-" + kind + ".json")
            spec_path.write_text(json.dumps({"files": files, "graphs": graphs, "videos": videos},
                                            indent=2) + "\n")
            recipe = {"format": "worker-fixture-recipe",
                      "sources": [{"path": "fixture-source-note.json",
                                   "source": "work/" + HERE.name + "/fixture-source-note.json",
                                   "sha256": _sha(note)}],
                      "generator": {"source": "work/" + HERE.name + "/" + spec_path.name,
                                    "sha256": _sha(spec_path)}}
            recipe_path = HERE / ("fixture-recipe-" + kind + ".json")
            recipe_path.write_text(json.dumps(recipe, indent=2) + "\n")
            built.append({"case_id": case, "recipe": str(recipe_path.relative_to(ROOT)),
                          "spec_sha256": _sha(spec_path)})
    return built


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
