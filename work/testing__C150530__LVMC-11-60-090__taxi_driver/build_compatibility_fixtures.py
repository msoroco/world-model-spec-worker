"""Build explicitly synthetic, case-specific text fixture recipes.

These exercise saved software paths only. The example capture graph is a schema
seed and cannot establish actual CARLA geometry, pixels, or legal context.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

from candidate_opendrive import build as build_map
from stand_route import make
from taxi_native_motion import route_points

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from test_turn_trace_finalizer import SavedNativeTraceTest, interpolate_path


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_source(folder: Path, relative: str, data: str) -> dict:
    path = folder / "diagnostic-sources" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data)
    return {"path": relative, "source": path.relative_to(REPO).as_posix(),
            "sha256": sha(path.read_bytes())}


def build(case: str, example: dict) -> None:
    fixture = SavedNativeTraceTest("test_original_frame_route_yields_right_turn_measurement")
    fixture.setUp()
    try:
        if case == "near_stand_straight":
            fixture.test_straight_attempt_yields_non_right_turn_measurement()
        elif case == "far_stand":
            layout = make(case)
            fixture.case = case
            fixture.layout.write_text(json.dumps(layout))
            fixture.map.write_bytes(build_map(case))
            fixture.context["case_id"] = fixture.context["assignment_id"] + "__" + case
            fixture.context["map_sha256"] = sha(fixture.map.read_bytes())
            fixture.context["stand_center_m"] = layout["stand"]["center"]
            fixture.context["notice_point_m"] = layout["posted_notice"]["point"]
            fixture.context_packet.write_text(json.dumps(fixture.context))
            fixture.rows = interpolate_path(route_points(layout), case)
            fixture.write_sources()
        folder = ROOT / "cases" / case
        rows = fixture.rows
        sources = []
        for name in ("original-trace.jsonl", "original-trace-seal.json",
                     "reviewed-context.json"):
            sources.append(write_source(folder, name, (fixture.root / name).read_text()))
        for path in sorted((fixture.root / "reviewed_sources").iterdir()):
            sources.append(write_source(folder, "reviewed_sources/" + path.name,
                                        path.read_text()))
        trace = []
        mapping = []
        controls = []
        events = []
        frames = []
        graphs = []
        event_seed = json.loads(example["files"]["capture/evidence.jsonl"].splitlines()[0])
        frame_seed = json.loads(example["files"]["capture/native/frames.jsonl"].splitlines()[0])
        for index, row in enumerate(rows):
            frame, time_s = row["frame"], row["time_s"]
            trace.append({"frame": frame, "time_s": time_s,
                          "position": {"x": row["x_m"], "y": row["y_m"], "z": 0},
                          "position_m": row["position_m"], "heading_deg": row["yaw_deg"],
                          "speed_mps": 5.0, "speed_mph": 5.0 / .44704,
                          "velocity_mps": [5 * math.cos(math.radians(row["yaw_deg"])),
                                           5 * math.sin(math.radians(row["yaw_deg"])), 0],
                          "control": {"throttle": 0.2, "brake": 0.0,
                                      "hand_brake": False, "steer": 0.0},
                          "road_id": row["road_id"]})
            mapping.append({"carla_frame": frame, "native_frame": frame,
                            "video_frame": index, "time_s": time_s})
            controls.append({"frame": frame, "time_s": time_s,
                             "control": {"steer": 0.0, "throttle": 0.2,
                                         "brake": 0.0, "finished": index == len(rows) - 1}})
            event = json.loads(json.dumps(event_seed))
            event.update(original_frame=frame, replay_frame=frame,
                         recording_time_s=time_s, replay_simulation_time_s=time_s)
            event["ego"].update(position_m=row["position_m"],
                                heading_deg=row["yaw_deg"], speed_mps=5.0)
            seed_position = event_seed["ego"]["position_m"]
            event["ego"]["body_vertices_m"] = [
                [vertex[axis] + row["position_m"][axis] - seed_position[axis]
                 for axis in range(3)]
                for vertex in event_seed["ego"]["body_vertices_m"]]
            event["original_observations"] = {
                "frame": frame, "time_s": time_s,
                "participants": [], "map_context": {},
                "world_settings": {"no_rendering_mode": False},
                "rgb_sensors": [{"actor_id": 209, "blueprint": "sensor.camera.rgb"}]}
            events.append(event)
            graph_path = f"capture/native/graphs/base/{frame:08d}.adapter.json"
            graph = {"path": graph_path,
                     "attributes": {"frame": frame, "simulation_time_s": time_s,
                                    "observed_evidence": event["original_observations"]},
                     "nodes": [], "edges": []}
            graphs.append(graph)
            native_frame = json.loads(json.dumps(frame_seed))
            native_frame["frame"] = frame
            native_frame["simulation_time"] = time_s
            native_frame["adapter_graph"] = graph_path.removeprefix("capture/native/")
            native_frame["nodes"] = 0
            native_frame["edges"] = 0
            frames.append(native_frame)
        for name, content in (
                ("trace.jsonl", "".join(json.dumps(r) + "\n" for r in trace)),
                ("video_frames.jsonl", "".join(json.dumps(r) + "\n" for r in mapping)),
                ("taxi-controller-history.jsonl", "".join(json.dumps(r) + "\n" for r in controls)),
                ("capture/evidence.jsonl", "".join(json.dumps(r) + "\n" for r in events)),
                ("capture/native/frames.jsonl", "".join(json.dumps(r) + "\n" for r in frames)),
                ("capture/native_map_facts.json", example["files"]["capture/native_map_facts.json"]),
                ("capture/recorder_info.txt", example["files"]["capture/recorder_info.txt"]),
                ("road.xodr", fixture.map.read_text()),
                ("carla_recorder.log", "synthetic fixture; no CARLA recording\n"),
                ("acquisition-provenance.json", json.dumps({"provenance_kind": "synthetic_fixture",
                                                        "diagnostic_fixture": True}) + "\n")):
            sources.append(write_source(folder, name, content))
        manifest = json.loads(example["files"]["capture/manifest.json"])
        manifest.update(case_id=fixture.context["case_id"], frames=len(rows),
                        source_run="synthetic C150530 CPU fixture")
        manifest["sources"] = {name: next(item["sha256"] for item in sources
                                        if item["path"] == name)
                               for name in ("road.xodr", "trace.jsonl", "carla_recorder.log")}
        sources.append(write_source(folder, "capture/manifest.json",
                                    json.dumps(manifest, indent=2) + "\n"))
        specification = {"files": {}, "graphs": graphs,
                         "videos": [{**video, "frames": len(rows)}
                                    for video in example["videos"]]}
        spec_path = folder / "diagnostic.json"
        spec_path.write_text(json.dumps(specification, separators=(",", ":")) + "\n")
        recipe = {"format": "worker-fixture-recipe", "sources": sources,
                  "generator": {"source": spec_path.relative_to(REPO).as_posix(),
                                "sha256": sha(spec_path.read_bytes())}}
        (folder / "fixture-recipe.json").write_text(json.dumps(recipe, indent=2) + "\n")
    finally:
        fixture.doCleanups()


if __name__ == "__main__":
    example = json.loads((REPO / "runtime" / "fixtures" / "example.json").read_text())
    for case in ("near_stand", "far_stand", "near_stand_straight"):
        build(case, example)
