"""Build explicit, source-hashed CPU rail fixtures; no physical capture claim."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile

from rail_native_capture import CAMERAS
from rail_sight_measurement import measure

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work/c410753-fixture-build"


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def build_one(case):
    key = case["case_id"].removeprefix(HERE.name + "__")
    scratch = Path(tempfile.mkdtemp(prefix=key + "-", dir=SCRATCH))
    files = {}

    def add(name, value):
        text = value if isinstance(value, str) else encoded(value)
        files[name] = text
        path = scratch / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return {"path": name, "sha256": sha(text)}

    road = ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            "<OpenDRIVE><header revMajor=\"1\" revMinor=\"4\" name=\"diagnostic railway approach\" version=\"1\" "
            "north=\"10\" south=\"-10\" east=\"500\" west=\"-100\" vendor=\"worker-diagnostic\"/>"
            "<road name=\"synthetic railway approach\" length=\"600\" id=\"410753\" junction=\"-1\">"
            "<link/><planView><geometry s=\"0\" x=\"-100\" y=\"0\" hdg=\"0\" length=\"600\"><line/></geometry></planView>"
            "<elevationProfile><elevation s=\"0\" a=\"0\" b=\"0\" c=\"0\" d=\"0\"/></elevationProfile>"
            "<lateralProfile/><lanes><laneOffset s=\"0\" a=\"0\" b=\"0\" c=\"0\" d=\"0\"/>"
            "<laneSection s=\"0\"><center><lane id=\"0\" type=\"none\" level=\"false\"/></center>"
            "<right><lane id=\"-1\" type=\"driving\" level=\"false\"><width sOffset=\"0\" a=\"4\" b=\"0\" c=\"0\" d=\"0\"/></lane></right>"
            "</laneSection></lanes></road></OpenDRIVE>\n")
    map_ref = add("diagnostic-road.xodr", road)
    review_ref = add("diagnostic-review.json", {
        "road_sha256": sha(road), "grade_crossing": True,
        "railway_kind": "electric", "track_extent_each_direction_ft": 400,
        "approach_extent_ft": 100, "municipal_jurisdiction": True,
        "diagnostic_fixture": True})
    packet = {"assignment_id": HERE.name, "case_id": case["case_id"],
              "diagnostic_fixture": True, "road_sha256": sha(road),
              "original_map_source": map_ref, "railway_review_source": review_ref}
    packet_ref = add("reviewed-rail-packet.json", packet)
    mph = case["engineering_target_traversal_mph"]
    speed = mph / 2.2369362920544
    obstructed = case["engineering_sight_setup"] == "obscured"
    exception = case["exception_setup"]
    frames, cameras = [], []
    observed_keys = ("original_frame", "time_s", "route_station_m", "speed_mps",
                     "position_xy_m", "body_on_crossing", "flagman_on_duty",
                     "signal_installed", "signal_clearly_visible",
                     "signal_immediate_train_approach")
    for index in range(900):
        frame = {"original_frame": index, "time_s": index * .05,
                 "route_station_m": index * speed * .05,
                 "speed_mps": speed, "velocity_mps": [speed, 0.0, 0.0],
                 "position_xy_m": [index * speed * .05, 0.0],
                 "body_on_crossing": 300 <= index < 350,
                 "flagman_on_duty": exception == "flagman_on_duty" and 300 <= index < 350,
                 "signal_installed": exception in ("visible_nonwarning_signal", "visible_warning_signal"),
                 "signal_clearly_visible": exception in ("visible_nonwarning_signal", "visible_warning_signal"),
                 "signal_immediate_train_approach": exception == "visible_warning_signal"}
        ray = {"frame": index, "crossing": True,
               "rail_minus_400ft": not (obstructed and index == 299),
               "rail_plus_400ft": True}
        exception_ref = add(f"original-exceptions/{index:08d}.json", {
            "frame": index, **{name: frame[name] for name in observed_keys[6:]}})
        source_ref = add(f"original-frames/{index:08d}.json", {
            **frame, "exception_source_trace": exception_ref})
        ray_ref = add(f"original-rays/{index:08d}.json", ray)
        frames.append({**frame, "sight_crossing_clear": ray["crossing"],
                       "sight_rail_negative_400ft_clear": ray["rail_minus_400ft"],
                       "sight_rail_positive_400ft_clear": ray["rail_plus_400ft"],
                       "frame_source_path": source_ref["path"],
                       "frame_source_sha256": source_ref["sha256"],
                       "sight_source_path": ray_ref["path"],
                       "sight_source_sha256": ray_ref["sha256"]})
        cameras.append({"original_frame": index,
                        "sources": {name: {"sha256": "0" * 64} for name in CAMERAS}})
    frame_ref = add("native-rail-frames.json", frames)
    camera_ref = add("native-rail-camera-map.json", cameras)
    camera_map_source = files.pop("native-rail-camera-map.json")
    files["video_frames.jsonl"] = "".join(encoded({
        "video_frame": frame["original_frame"],
        "carla_frame": frame["original_frame"],
        "native_frame": frame["original_frame"],
        "time_s": frame["time_s"],
    }) for frame in frames)
    trace = [{"frame": row["original_frame"], "time_s": row["time_s"],
              "position": {"x": row["position_xy_m"][0], "y": 0.0, "z": 0.0},
              "position_m": [row["position_xy_m"][0], 0.0, 0.0],
              "heading_deg": 0.0, "speed_mps": row["speed_mps"],
              "speed_mph": row["speed_mps"] / 0.44704,
              "velocity_mps": row["velocity_mps"],
              "control": {}} for row in frames]
    trace_text = "".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n"
                         for row in trace)
    evidence, native_index, graphs = [], [], []
    for row in trace:
        index, time_s = row["frame"], row["time_s"]
        position = row["position_m"]
        observed = {"frame": index, "time_s": time_s, "participants": [],
                    "map_context": {"declared_public_way_road_ids": []}}
        body = [[position[0] + dx, position[1] + dy, z]
                for dx in (-2.0, 2.0) for dy in (-1.0, 1.0) for z in (0.0, 1.5)]
        evidence.append({"original_frame": index, "replay_frame": index,
                         "actor_id": 410753, "recording_time_s": time_s,
                         "replay_simulation_time_s": time_s,
                         "ego": {"position_m": position, "heading_deg": 0.0,
                                 "speed_mps": row["speed_mps"],
                                 "speed_provenance": "synthetic_native_sample",
                                 "body_vertices_m": body},
                         "original_observations": observed, "world": {"weather": {}}})
        relative_graph = f"graphs/base/{index:08d}.adapter.json"
        native_index.append({"adapter_graph": relative_graph, "frame": index,
                             "simulation_time": time_s})
        graphs.append({"path": "capture/native/" + relative_graph,
                       "attributes": {"frame": index, "time_s": time_s,
                                      "observed_evidence": observed},
                       "nodes": [], "edges": []})
    folder = HERE / "diagnostic-fixtures" / key
    folder.mkdir(parents=True, exist_ok=True)
    sources = []
    camera_map_path = folder / "source-native-rail-camera-map.json"
    camera_map_path.write_text(camera_map_source)
    sources.append({"path": "native-rail-camera-map.json",
                    "source": str(camera_map_path.relative_to(REPO)),
                    "sha256": sha(camera_map_source)})
    for name, value in {
        "road.xodr": road,
        "capture/evidence.jsonl": "".join(encoded(row) for row in evidence),
        "capture/native/frames.jsonl": "".join(encoded(row) for row in native_index),
        "capture/recorder_info.txt": "Create 410753: vehicle.tesla.model3 (rail diagnostic) at (0, 0, 0)\n",
        "capture/manifest.json": encoded({
            "acquisition": "original_live_run", "case_id": case["case_id"],
            "complete_driving_lanes": False, "extraction_confirmed": True,
            "frames": 900, "status": "draft", "sources": {
                "road.xodr": sha(road), "trace.jsonl": sha(trace_text)}}),
    }.items():
        source_path = folder / ("source-" + name.replace("/", "-"))
        source_path.write_text(value)
        sources.append({"path": name, "source": str(source_path.relative_to(REPO)),
                        "sha256": sha(value)})
    measurement = measure(scratch, packet, road, frames)
    add("native-rail-receipt.json", {
        "case_id": case["case_id"], "capture_kind": "diagnostic_fixture",
        "fps": 20, "duration_s": 45, "frame_count": 900,
        "packet": packet_ref, "frames": frame_ref, "camera_map": camera_ref,
        "measurement": measurement, "legal_conclusion": None})
    spec = {"files": files, "graphs": graphs,
            "videos": [{"path": name + ".mkv", "frames": 900,
                        "width": size[0], "height": size[1], "fps": 20,
                        "color": "black"} for name, size in CAMERAS.items()]}
    spec_path = folder / "fixture-spec.json"
    spec_path.write_text(json.dumps(spec, sort_keys=True, separators=(",", ":")) + "\n")
    recipe = {"format": "worker-fixture-recipe", "sources": sources + [
        {"path": "fixture-source.txt", "source": "work/" + HERE.name + "/diagnostic-source.txt",
         "sha256": sha((HERE / "diagnostic-source.txt").read_text())}],
        "generator": {"source": str(spec_path.relative_to(REPO)),
                      "sha256": hashlib.sha256(spec_path.read_bytes()).hexdigest()}}
    (folder / "fixture-recipe.json").write_text(json.dumps(recipe, indent=2, sort_keys=True) + "\n")
    if spec_path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("diagnostic fixture spec exceeds work file limit")
    return key, spec_path.stat().st_size


def build():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    marker = HERE / "diagnostic-source.txt"
    marker.write_text("Synthetic rail compatibility fixture; no original CARLA observation.\n")
    plan = json.loads((HERE / "case-plan.json").read_text())
    return [build_one(case) for case in plan["cases"]]


if __name__ == "__main__":
    print(build())
