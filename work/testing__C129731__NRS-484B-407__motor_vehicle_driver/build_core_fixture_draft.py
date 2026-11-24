"""Build bounded, diagnostic-only 900-frame Core/video fixture specifications.

This is a software wiring fixture. Its flat color videos and generated graph
records are never evidence of a physical U-turn or driver visibility.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))


def compact(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), allow_nan=False)


def lines(rows: list[dict]) -> str:
    return "".join(compact(row) + "\n" for row in rows)


def build(suffix: str) -> dict:
    folder = HERE / "fixtures" / suffix
    inventory = json.loads((folder / "inventory.json").read_text())
    frame_map = json.loads((folder / "frame_map.json").read_text())["frames"]
    motion = json.loads((folder / "ego_motion.json").read_text())["samples"]
    if len(frame_map) != len(motion) or len(frame_map) != 900:
        raise ValueError("Full diagnostic sight timeline required")
    original = json.loads((REPO / "runtime/fixtures/example.json").read_text())
    road = original["files"]["road.xodr"]
    road = road.replace("C10301 long synthetic alley with adjacent marked access aisle",
                        "C129731 diagnostic curved road")
    road = road.replace('<line /></geometry>', '<arc curvature="0.001" /></geometry>')
    if road == original["files"]["road.xodr"]:
        raise ValueError("Diagnostic curve geometry not constructed")
    trace = []
    mapping = []
    evidence = []
    native_frames = []
    graphs = []
    vertices = [[-2.5, -1, 0], [-2.5, -1, 1.5], [2.5, -1, 0],
                [2.5, -1, 1.5], [2.5, 1, 0], [2.5, 1, 1.5],
                [-2.5, 1, 0], [-2.5, 1, 1.5]]
    for index, (frame, sample) in enumerate(zip(frame_map, motion)):
        number, time = frame["frame"], frame["time_s"]
        if sample["frame"] != number or sample["time_s"] != time:
            raise ValueError("Sight and diagnostic Core clocks differ")
        heading = sample["yaw_deg"]
        trace.append({"frame": number, "time_s": time,
                      "position": {"x": 0, "y": 0, "z": 0},
                      "position_m": [0, 0, 0], "heading_deg": heading,
                      "speed_mps": 0, "speed_mph": 0,
                      "velocity_mps": [0, 0, 0], "control": {}})
        mapping.append({"video_frame": index, "carla_frame": number,
                        "time_s": time})
        observed = {"frame": number, "time_s": time,
                    "participants": [],
                    "map_context": {"declared_public_way_road_ids": []}}
        evidence.append({"actor_id": 7, "original_frame": number,
                         "replay_frame": number,
                         "recording_time_s": time,
                         "replay_simulation_time_s": time,
                         "ego": {"position_m": [0, 0, 0],
                                 "heading_deg": heading, "speed_mps": 0,
                                 "speed_provenance": "diagnostic synthetic sample",
                                 "body_vertices_m": vertices},
                         "original_observations": observed,
                         "world": {"weather": {}}})
        graph_path = f"capture/native/graphs/base/{number:08d}.adapter.json"
        native_frames.append({"frame": number, "simulation_time": time,
                              "adapter_graph": f"graphs/base/{number:08d}.adapter.json"})
        graphs.append({"path": graph_path,
                       "attributes": {"frame": number, "time_s": time,
                                      "observed_evidence": observed},
                       "nodes": [], "edges": []})
    trace_text = lines(trace)
    manifest = {"status": "draft", "acquisition": "diagnostic_synthetic_fixture",
                "case_id": inventory["case_id"], "frames": 900,
                "complete_driving_lanes": False,
                "extraction_confirmed": True,
                "sources": {"road.xodr": hashlib.sha256(road.encode()).hexdigest(),
                            "trace.jsonl": hashlib.sha256(trace_text.encode()).hexdigest()}}
    files = {"road.xodr": road, "trace.jsonl": trace_text,
             "video_frames.jsonl": lines(mapping),
             "capture/evidence.jsonl": lines(evidence),
             "capture/native/frames.jsonl": lines(native_frames),
             "capture/manifest.json": compact(manifest) + "\n",
             "capture/recorder_info.txt":
                 "Create 7: vehicle.tesla.model3 (diagnostic subject) at (0, 0, 0)\n",
             "fixture-provenance.json": compact({"diagnostic_fixture": True,
                 "scope": "Core/video software wiring only; no physical or legal acceptance"}) + "\n"}
    videos = [{"path": name + ".mkv", "frames": 900,
               "width": width, "height": height, "fps": 20, "color": "black"}
              for name, width, height in CAMERAS]
    spec = {"files": files, "graphs": graphs, "videos": videos}
    for name, value in files.items():
        if len(value.encode()) > 2 * 1024 * 1024:
            raise ValueError("Diagnostic text exceeds return limit: " + name)
    return spec


def main() -> None:
    for suffix in ("distance_reference", "distance_below_500ft",
                   "distance_at_500ft", "distance_above_500ft"):
        value = build(suffix)
        target = HERE / "fixtures" / suffix / "core-diagnostic.draft.json"
        target.write_text(compact(value) + "\n")
        if target.stat().st_size > 2 * 1024 * 1024:
            target.unlink()
            raise ValueError("Diagnostic specification exceeds return limit")
        print(suffix, target.stat().st_size)


if __name__ == "__main__":
    main()
