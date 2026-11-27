"""Explicit synthetic saved fixtures for software proof, never physical evidence."""

import hashlib
import json
from pathlib import Path

from prove_tunnel import context as diagnostic_context, trace as diagnostic_trace


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = HERE.name
NAMES = ("overview", "approach", "reference_corner", "driver_reference")
SOURCE_NAMES = ("road.xodr", "portal-geometry.json", "road-direction-survey.json",
    "centreline-geometry.json", "vehicle-extents.jsonl", "sight-rays.jsonl",
    "tunnel-rows.jsonl", "trace.jsonl", "video_frames.jsonl", "capture/evidence.jsonl")


def encode(value):
    return json.dumps(value, indent=2, allow_nan=False) + "\n"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encode(value))


def lines(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, allow_nan=False) + "\n" for row in values))


def vertices(corners):
    return [[x, y, z] for x, y in corners for z in (0.0, 1.5)]


def build(suffix):
    case_id = ASSIGNMENT + "__" + suffix
    out = HERE / "fixture-source" / suffix
    out.mkdir(parents=True, exist_ok=True)
    rows = diagnostic_trace(left=suffix == "probe_2")
    for i, row in enumerate(rows):
        row["native_frame"] = i
    put(out / "portal-geometry.json", {"structure_kind": "tunnel",
        "portal_x_m": 0.0, "tunnel_prop": "synthetic_diagnostic_only",
        "physical_tunnel_verified": False})
    put(out / "road-direction-survey.json", {"lanes": [-1, 1],
        "one_way_native_survey": False, "original_native_observed": False})
    put(out / "centreline-geometry.json", {"centerline_y_m": 0.0,
        "source": "synthetic diagnostic OpenDRIVE centerline"})
    lines(out / "vehicle-extents.jsonl", [{"native_frame": i,
        "body_xy_m": row["body_xy_m"]} for i, row in enumerate(rows)])
    lines(out / "sight-rays.jsonl", [{"native_frame": i,
        "incoming_lane_sight_ray": row["incoming_lane_sight_ray"]}
        for i, row in enumerate(rows)])
    lines(out / "tunnel-rows.jsonl", rows)
    lines(out / "video_frames.jsonl", [{"video_frame": i,
        "native_frame": i, "time_s": i / 20} for i in range(600)])
    traces = []
    evidence = []
    graphs = []
    frame_rows = []
    for i, row in enumerate(rows):
        corners = row["body_xy_m"]
        x = sum(point[0] for point in corners) / 4
        y = sum(point[1] for point in corners) / 4
        speed = row["observed_speed_mps"]
        trace = {"frame": i, "time_s": i / 20, "position": {"x": x, "y": y, "z": .5},
            "position_m": [x, y, .5], "heading_deg": 0,
            "velocity_mps": [speed, 0, 0], "speed_mps": speed,
            "speed_mph": speed * 2.2369362921,
            "control": {"throttle": 0, "brake": 0, "hand_brake": False}}
        traces.append(trace)
        evidence.append({"actor_id": 107, "ego": {"body_vertices_m": vertices(corners),
            "heading_deg": 0, "position_m": [x, y, .5], "speed_mps": speed,
            "speed_provenance": "synthetic_native_sample", "synthetic_diagnostic": True},
            "original_frame": i, "recording_time_s": i / 20,
            "replay_frame": i, "replay_simulation_time_s": i / 20,
            "world": {"road_projection": {"lane_id": 1 if y > 0 else -1,
                "road_id": 313130, "s_m": x + 100, "section_id": 0},
                "weather": {"cloudiness": 0, "fog_density": 0,
                            "precipitation": 0, "wetness": 0}}})
        graph_path = f"capture/native/graphs/base/{i:08d}.adapter.json"
        graphs.append({"path": graph_path, "attributes": {"frame": i,
            "simulation_time_s": i / 20, "source": "C313130 tunnel CPU diagnostic",
            "synthetic_diagnostic": True}, "edges": [],
            "nodes": [{"id": "ego", "attributes": {"entity_id": 107,
                "forward": [1.0, 0.0, 0.0], "sem_class": "ego",
                "threedbbox": vertices(corners), "vertex": [x, y, .5]}}]})
        frame_rows.append({"frame": i, "simulation_time": i / 20,
            "adapter_graph": graph_path.removeprefix("capture/native/"),
            "base": graph_path.removeprefix("capture/native/"),
            "nodes": 1, "edges": 0})
    lines(out / "trace.jsonl", traces)
    lines(out / "capture/evidence.jsonl", evidence)
    put(out / "capture/manifest.json", {"extraction_confirmed": True,
        "frames": 600, "synthetic_diagnostic": True,
        "sources": {"road.xodr": hashlib.sha256(
            json.loads((HERE / ("selected-construction-" + suffix + ".json")).read_text())
            ["files"][1]["content"].encode()).hexdigest(),
            "trace.jsonl": sha(out / "trace.jsonl")}})
    spec = {"files": {"capture/native/frames.jsonl": "".join(
        json.dumps(v, separators=(",", ":")) + "\n" for v in frame_rows),
        "capture/recorder_info.txt": "synthetic CPU diagnostic; no CARLA recorder\nCreate 107: vehicle.tesla.model3 (0)\n"},
        "graphs": graphs, "videos": [{"path": name + ".mkv", "width":
            1920 if name == "overview" else 1280, "height":
            1080 if name == "overview" else 720, "fps": 20,
            "frames": 600, "color": "black"} for name in NAMES]}
    spec_path = HERE / ("fixture-spec-" + suffix + ".json")
    spec_path.write_text(encode(spec))
    source_files = {name: name for name in SOURCE_NAMES}
    source_hashes = {name: sha(out / name) for name in SOURCE_NAMES if name != "road.xodr"}
    road = next(item["content"] for item in json.loads((HERE / (
        "selected-construction-" + suffix + ".json")).read_text())["files"]
        if item["path"] == "road.xodr")
    source_hashes["road.xodr"] = hashlib.sha256(road.encode()).hexdigest()
    context = diagnostic_context()
    context.update({"case_id": case_id, "source_files": source_files,
        "source_sha256": source_hashes,
        "native_map_sha256": hashlib.sha256(road.encode()).hexdigest(),
        "portal_geometry_sha256": source_hashes["portal-geometry.json"],
        "road_direction_survey_sha256": source_hashes["road-direction-survey.json"],
        "centreline_geometry_sha256": source_hashes["centreline-geometry.json"],
        "vehicle_extent_sha256": source_hashes["vehicle-extents.jsonl"],
        "sight_ray_source_sha256": source_hashes["sight-rays.jsonl"]})
    put(out / "tunnel-context.json", context)
    put(out / "acquisition-provenance.json", {"provenance_kind": "synthetic_fixture",
        "diagnostic_fixture": True, "original_native_observed": False})
    source_list = ["portal-geometry.json", "road-direction-survey.json",
        "centreline-geometry.json", "vehicle-extents.jsonl", "sight-rays.jsonl",
        "tunnel-rows.jsonl", "trace.jsonl", "video_frames.jsonl",
        "capture/evidence.jsonl", "capture/manifest.json", "tunnel-context.json",
        "acquisition-provenance.json"]
    recipe = {"format": "worker-fixture-recipe",
        "generator": {"source": str(spec_path.relative_to(REPO)), "sha256": sha(spec_path)},
        "sources": [{"path": name, "sha256": sha(out / name),
                     "source": str((out / name).relative_to(REPO))}
                    for name in source_list]}
    path = HERE / ("selected-recipe-" + suffix + ".json")
    path.write_text(encode(recipe))
    return path


if __name__ == "__main__":
    for suffix in ("probe_1", "probe_2"):
        path = build(suffix)
        print(json.dumps({"recipe": path.name, "sha256": sha(path)}))
