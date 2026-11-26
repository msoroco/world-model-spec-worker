"""Generate small textual, source-shaped CPU diagnostics for exact cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ASSIGNMENT = HERE.parent.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(rows):
    return "".join(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n"
                   for row in rows)


def build(letter):
    if letter not in ("a", "b"):
        raise ValueError("Unknown exact case")
    yaw = 45 if letter == "a" else 70
    case = ASSIGNMENT + "__selected_03f318de__condition_" + letter
    provenance = "synthetic_cpu_fixture"
    context = {"provenance": provenance, "native_road_id": 1,
        "case_id": case, "space_id": "angle_space_1", "activity": "parked",
        "native_actor_id": 17, "native_blueprint": "vehicle.lincoln.mkz_2020",
        "original_body_and_activity_review_required": True}
    device = {"provenance": provenance, "native_road_id": 1,
        "device_id": "902", "device_kind": "official_angle_parking_control",
        "governs_space_id": "angle_space_1",
        "indicated_angle_to_curb_deg": 45,
        "official_device_review_required": True,
        "actual_sign_pixels_and_authority_unverified": True}
    road = {"provenance": provenance, "native_road_id": 1,
        "space_id": "angle_space_1", "driving_lane_id": -1,
        "parking_lane_id": -2, "curb_tangent_heading_deg": 0,
        "curb_side": "right", "authored_space_center_xy_m": [6.5, 0],
        "actual_curb_and_space_pixels_review_required": True}
    samples, bodies, joins, traces, evidence, frames, graphs = [], [], [], [], [], [], []
    for i in range(600):
        native, time_s = 1000+i, (i+1)/20
        common = {"case_id": case, "provenance": provenance,
            "native_frame": native, "time_s": time_s}
        vertices = [[6.5+dx, dy, .5] for dx, dy in
                    ((-.7, -.4), (-.7, .4), (.7, .4), (.7, -.4))]
        samples.append({**common, "sample_index": i, "native_road_id": 1,
            "native_lane_id": -2, "space_id": "angle_space_1",
            "ego_heading_deg": yaw, "ego_speed_mps": 0,
            "activity": "parked", "control": {"brake": 0, "hand_brake": True}})
        bodies.append({**common, "body_vertices_m": vertices})
        joins.append({**common, "video_frame": i, "carla_frame": native})
        traces.append({"frame": native, "time_s": time_s,
            "position": {"x": 6.5, "y": 0, "z": .5},
            "position_m": [6.5, 0, .5], "heading_deg": yaw,
            "speed_mps": 0, "speed_mph": 0,
            "velocity_mps": [0, 0, 0],
            "control": {"throttle": 0, "brake": 0, "hand_brake": True}})
        evidence.append({"original_frame": native, "recording_time_s": time_s,
            "replay_frame": native, "replay_simulation_time_s": time_s,
            "actor_id": 17, "ego": {"position_m": [6.5, 0, .5],
                "heading_deg": yaw, "speed_mps": 0,
                "body_vertices_m": vertices,
                "speed_provenance": "synthetic_native_sample",
                "synthetic_diagnostic": True},
            "world": {"weather": {"cloudiness": 0, "precipitation": 0,
                "wetness": 0, "fog_density": 0},
                "road_projection": {"road_id": 1, "section_id": 0,
                    "lane_id": -2, "s_m": 70}}})
        graph = f"graphs/base/{native:08d}.adapter.json"
        frames.append({"frame": native, "simulation_time": time_s,
            "time_s": time_s, "base": graph, "adapter_graph": graph,
            "synthetic_diagnostic": True})
        graphs.append({"path": "capture/native/" + graph,
            "attributes": {"frame": native}, "nodes": [], "edges": []})
    files = {"official_device.json": json.dumps(device) + "\n",
        "road_geometry.json": json.dumps(road) + "\n",
        "parking_context.json": json.dumps(context) + "\n",
        "native_samples.jsonl": lines(samples), "body_history.jsonl": lines(bodies),
        "video_frames.jsonl": lines(joins), "trace.jsonl": lines(traces),
        "capture/evidence.jsonl": lines(evidence),
        "capture/native/frames.jsonl": lines(frames),
        "capture/recorder_info.txt": "Create 17: vehicle.lincoln.mkz_2020\n",
        "road.xodr": (HERE / "angle-bay-road.xodr").read_text()}
    files["capture/manifest.json"] = json.dumps({"extraction_confirmed": True,
        "frames": 600, "synthetic_diagnostic": True,
        "sources": {"road.xodr": hashlib.sha256(files["road.xodr"].encode()).hexdigest(),
            "trace.jsonl": hashlib.sha256(files["trace.jsonl"].encode()).hexdigest()}},
        separators=(",", ":")) + "\n"
    videos = [{"path": name + ".mkv", "frames": 600,
        "width": width, "height": height, "fps": 20, "color": "blue"}
        for name, width, height in (("overview", 1920, 1080),
            ("approach", 1280, 720), ("reference_corner", 1280, 720),
            ("driver_reference", 1280, 720))]
    spec = HERE / f"selected-{letter}-fixture.json"
    spec.write_text(json.dumps({"files": files, "graphs": graphs,
        "videos": videos}, separators=(",", ":"), allow_nan=False) + "\n")
    if spec.stat().st_size > 2*1024*1024:
        raise ValueError("Returned fixture specification exceeds 2 MiB")
    assignment = ROOT / "inputs" / ASSIGNMENT / "assignment.json"
    recipe = {"format": "worker-fixture-recipe", "sources": [{
        "path": "diagnostic-input-assignment.json",
        "source": str(assignment.relative_to(ROOT)), "sha256": sha(assignment)}],
        "generator": {"source": str(spec.relative_to(ROOT)), "sha256": sha(spec)}}
    target = HERE / f"selected-{letter}-fixture-recipe.json"
    target.write_text(json.dumps(recipe, indent=2) + "\n")
    return {"case_id": case, "spec_bytes": spec.stat().st_size,
            "spec_sha256": sha(spec), "recipe_sha256": sha(target)}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", required=True, choices=("a", "b"))
    args = parser.parse_args()
    print(json.dumps(build(args.condition), sort_keys=True))
