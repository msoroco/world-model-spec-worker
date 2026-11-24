"""Extend a crosswalk diagnostic packet with a source joined Core capture.

The graph and telemetry are synthetic software test data. They carry no
physical visibility or crosswalk marking claim.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from case_construction import CASES
from crosswalk_measurements import ASSIGNMENT_ID

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EXAMPLE = json.loads((REPO / "runtime/fixtures/example.json").read_text())
GRAPH = json.loads((HERE / "diagnostic-graph-template.json").read_text())
EVENT = json.loads(EXAMPLE["files"]["capture/evidence.jsonl"].splitlines()[0])


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n")


def write_rows(path: Path, rows: list[dict]) -> None:
    write(path, "\n".join(json.dumps(row, separators=(",", ":"), allow_nan=False)
                           for row in rows))


def build(suffix: str) -> dict:
    if suffix not in CASES:
        raise ValueError("unknown exact case")
    source = HERE / "diagnostic_sources" / suffix
    trace = [json.loads(line) for line in (source / "trace.jsonl").read_text().splitlines()]
    if len(trace) != 900:
        raise ValueError("diagnostic source must contain 900 original ticks")
    events, indices = [], []
    for row in trace:
        frame, time_s = row["frame"], row["time_s"]
        x, y = row["ego_center"]
        speed = row["ego_speed_mps"]
        position = [x, y, 0.0]
        row.update(position={"x": x, "y": y, "z": 0.0}, position_m=position,
                   heading_deg=0.0, speed_mps=speed, speed_mph=speed / .44704,
                   velocity_mps=[speed, 0.0, 0.0],
                   control={"throttle": 0.0, "steer": 0.0, "brake": 0.0,
                            "hand_brake": False, "reverse": False,
                            "manual_gear_shift": False, "gear": 0})
        event = copy.deepcopy(EVENT)
        event.update(original_frame=frame, replay_frame=frame, actor_id=10,
                     recording_time_s=time_s, replay_simulation_time_s=time_s + 13.5)
        event["ego"].update(position_m=position, heading_deg=0.0, speed_mps=speed,
                            speed_provenance="synthetic_native_sample",
                            body_vertices_m=row["ego_vertices"])
        event["world"]["road_projection"].update(road_id=1, section_id=0, lane_id=-1,
                                                  s_m=max(x, 0.0))
        observed = event["original_observations"]
        observed.update(frame=frame, time_s=time_s, participants=[], relations=[],
                        devices=[], rgb_sensors=[{"actor_id": 209,
                                                  "blueprint": "sensor.camera.rgb"}])
        observed.pop("map_context", None)
        events.append(event)
        graph = copy.deepcopy(GRAPH)
        graph["metadata"].update(frame=frame, simulation_time_s=time_s + 13.5,
                                 observed_evidence=observed)
        ego = next(node for node in graph["nodes"] if node["id"] == "ego")
        ego["attributes"].update(vertex=position, entity_id=10,
                                 threedbbox=row["ego_vertices"],
                                 carla_speed=speed, carla_vel_x=speed,
                                 carla_vel_y=0.0, carla_vel_z=0.0)
        original = ego["attributes"].get("original_observation")
        if original is not None:
            original.update(actor_id=10, position_m=position, heading_deg=0.0,
                            velocity_mps=[speed, 0.0, 0.0], speed_mps=speed,
                            body_vertices_m=row["ego_vertices"])
        relative = f"graphs/base/{frame:08d}.adapter.json"
        write(source / "capture/native" / relative,
              json.dumps(graph, separators=(",", ":"), allow_nan=False))
        indices.append({"frame": frame, "simulation_time": time_s + 13.5,
                        "abstract": None, "base": None,
                        "nodes": len(graph["nodes"]), "edges": len(graph["edges"]),
                        "extraction_seconds": 0.0, "capture_seconds": 0.0,
                        "adapter_graph": relative})
    write_rows(source / "trace.jsonl", trace)
    receipt = json.loads((source / "receipt.json").read_text())
    receipt["trace_sha256"] = sha(source / "trace.jsonl")
    write(source / "receipt.json", json.dumps(receipt, sort_keys=True))
    write_rows(source / "capture/evidence.jsonl", events)
    write_rows(source / "capture/native/frames.jsonl", indices)
    for name in ("road.xodr", "capture/native_map_facts.json",
                 "capture/recorder_info.txt"):
        content = EXAMPLE["files"][name]
        if name == "capture/recorder_info.txt":
            content = content.replace("Create 205:", "Create 10:")
        write(source / name, content)
    write(source / "carla_recorder.log", "synthetic diagnostic recorder placeholder")
    manifest = json.loads(EXAMPLE["files"]["capture/manifest.json"])
    manifest.update(status="diagnostic", acquisition="synthetic_fixture",
                    case_id=ASSIGNMENT_ID + "__" + suffix,
                    source_run="synthetic:crosswalk-converter-diagnostic",
                    frames=len(trace), extraction_confirmed=True,
                    observation_contract_version=0)
    manifest["sources"] = {name: sha(source / name) for name in
                           ("road.xodr", "trace.jsonl", "carla_recorder.log")}
    manifest["native_map_facts"]["sha256"] = sha(source / "capture/native_map_facts.json")
    write(source / "capture/manifest.json", json.dumps(manifest, separators=(",", ":")))
    recipe_path = HERE / ("fixture-recipe-" + suffix + ".json")
    recipe = json.loads(recipe_path.read_text())
    recipe["sources"] = [{"path": path.relative_to(source).as_posix(),
                          "source": path.relative_to(REPO).as_posix(),
                          "sha256": sha(path)}
                         for path in sorted(source.rglob("*")) if path.is_file()]
    write(recipe_path, json.dumps(recipe, indent=2))
    return {"case_id": ASSIGNMENT_ID + "__" + suffix,
            "source_count": len(recipe["sources"]), "recipe_sha256": sha(recipe_path)}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("suffix", choices=CASES)
    print(json.dumps(build(parser.parse_args().suffix), indent=2))
