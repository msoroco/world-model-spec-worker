"""Generate 900-frame textual software fixtures; never original evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name
CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))


def write(path, value):
    path.write_text(json.dumps(value, separators=(",", ":")) + "\n", encoding="utf-8")


def scene(case):
    return {"format": "synthetic-diagnostic-lane-split-v1", "case_id": case["case_id"],
            "operator_status": case["scenario_parameters"]["operator_status"],
            "performance_of_duty": case["scenario_parameters"]["performance_of_duty"],
            "ego_vehicle_class": case["scenario_parameters"]["vehicle_class"],
            "classification_source_sha256": "synthetic-chapter-classification",
            "operator_identity_source_sha256": "synthetic-operator-identity",
            "police_status_source_sha256": "synthetic-police-status",
            "performance_of_duty_source_sha256": "synthetic-duty-status",
            "map_id": "synthetic-one-way-multilane",
            "lanes": {"left": {"road_id": 4, "lane_id": -1},
                      "right": {"road_id": 4, "lane_id": -2}},
            "participant_readback": {"ego": {"actor_id": 1, "lane_id": -1},
                                     "left_occupant": {"actor_id": 2, "lane_id": -1},
                                     "right_occupant": {"actor_id": 3, "lane_id": -2}}}


def actor(role, ident, lane, s_m, lateral, speed):
    return {"actor_id": ident, "lane_id": lane, "s_m": round(s_m, 4),
            "lateral_m": lateral, "half_length_m": 1.0,
            "half_width_m": .25 if role == "ego" else .6,
            "speed_mps": speed}


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    base = json.loads((REPO / "runtime/fixtures/example.json").read_text())
    first_trace = json.loads(base["files"]["trace.jsonl"].splitlines()[0])
    first_manifest = json.loads(base["files"]["capture/manifest.json"])
    for case in plan["cases"]:
        cid = case["case_id"]
        params = case["scenario_parameters"]
        suffix = cid.split("__")[-1]
        spec = {"files": {"road.xodr": base["files"]["road.xodr"],
                          "capture/recorder_info.txt": base["files"]["capture/recorder_info.txt"].replace("Create 205:", "Create 1:"),
                          "capture/native_map_facts.json": base["files"]["capture/native_map_facts.json"],
                          "fixture-provenance.json": json.dumps({"scope": "synthetic 900-frame diagnostic only",
                                                                 "case_id": cid}) + "\n"},
                "graphs": [], "videos": []}
        for name, width, height in CAMERAS:
            for i in range(900):
                spec["files"][f"cameras/{name}/{i:04d}.png"] = "fixture-image\n"
            spec["videos"].append({"path": name + ".mkv", "frames": 900,
                                   "width": width, "height": height,
                                   "fps": 20, "color": "black"})
        history, trace, mapping, evidence, frames = [], [], [], [], []
        for i in range(900):
            frame = 38033 + i
            time_s = round((i + 1) / 20, 10)
            replay_s = round(13.517531131161, 10) + time_s
            spec["graphs"].append({"path": f"capture/native/graphs/base/{frame:08d}.adapter.json",
                                   "attributes": {"frame": frame, "simulation_time_s": replay_s,
                                                  "units": {"position": "m", "carla_speed": "m/s"},
                                                  "observed_evidence": {
                                                      "frame": frame, "time_s": time_s,
                                                      "participants": [],
                                                      "rgb_sensors": [{"id": "synthetic-diagnostic-rgb"}],
                                                      "world_settings": {"no_rendering_mode": False}}},
                                   "nodes": [], "edges": []})
            left_speed = 2.5 if params["left_motion"] == "moving" else 0.0
            right_speed = 2.5 if params["right_motion"] == "moving" else 0.0
            ego_s = -15 + 4 * time_s
            lateral = 1.5 if params["maneuver"] == "between" else -2.0
            history.append({"frame": frame, "time_s": time_s,
                            "actors": {"ego": actor("ego", 1, -1, ego_s, lateral, 4.0),
                                       "left_occupant": actor("left", 2, -1, left_speed * time_s,
                                                              0.0, left_speed),
                                       "right_occupant": actor("right", 3, -2, right_speed * time_s,
                                                               3.0, right_speed)}})
            sample = dict(first_trace)
            sample["frame"] = frame
            sample["time_s"] = time_s
            sample["position"] = {"x": ego_s, "y": lateral, "z": 0.0}
            sample["position_m"] = [ego_s, lateral, 0.0]
            sample["speed_mps"] = 4.0
            sample["speed_mph"] = 8.947745
            trace.append(sample)
            mapping.append({"video_frame": i, "carla_frame": frame,
                            "native_frame": frame, "time_s": time_s})
            box = [[ego_s + x, lateral + y, z] for x in (-1.0, 1.0)
                   for y in (-.25, .25) for z in (0.0, 1.5)]
            evidence.append({"original_frame": frame, "replay_frame": frame,
                             "actor_id": 1, "recording_time_s": time_s,
                             "replay_simulation_time_s": replay_s,
                             "ego": {"position_m": [ego_s, lateral, 0.0],
                                     "heading_deg": 0.0, "speed_mps": 4.0,
                                     "speed_provenance": "synthetic_native_sample",
                                     "body_vertices_m": box},
                             "world": {"weather": {}},
                             "original_observations": {
                                 "participants": [],
                                 "rgb_sensors": [{"actor_id": 10,
                                                  "blueprint": "sensor.camera.rgb"}],
                                 "world_settings": {"no_rendering_mode": False}}})
            frames.append({"frame": frame, "simulation_time": replay_s,
                           "abstract": None, "base": None, "nodes": 0, "edges": 0,
                           "extraction_seconds": 0.0, "capture_seconds": 0.0,
                           "adapter_graph": f"graphs/base/{frame:08d}.adapter.json"})
        spec["files"]["lane-split-scene.json"] = json.dumps(scene(case)) + "\n"
        spec["files"]["lane-split-history.jsonl"] = "".join(json.dumps(row, separators=(",", ":")) + "\n"
                                                                  for row in history)
        spec["files"]["trace.jsonl"] = "".join(json.dumps(row, separators=(",", ":")) + "\n"
                                                     for row in trace)
        spec["files"]["video_frames.jsonl"] = "".join(json.dumps(row, separators=(",", ":")) + "\n"
                                                            for row in mapping)
        spec["files"]["diagnostic-source-note.json"] = json.dumps({
            "source_kind": "synthetic_diagnostic_fixture", "accepted_original_source": False,
            "case_id": cid}) + "\n"
        first_manifest.update(case_id=cid, frames=900, required_observations=[],
                              source_run="synthetic-diagnostic-900-frames",
                              observation_contract_version=2,
                              complete_driving_lanes=False)
        first_manifest["sources"] = {
            "road.xodr": hashlib.sha256(spec["files"]["road.xodr"].encode()).hexdigest(),
            "trace.jsonl": hashlib.sha256(spec["files"]["trace.jsonl"].encode()).hexdigest()}
        spec["files"]["capture/manifest.json"] = json.dumps(first_manifest) + "\n"
        capture_sources = {}
        for relative, content in (("capture/evidence.jsonl", evidence),
                                  ("capture/native/frames.jsonl", frames)):
            source_path = ROOT / ("diagnostic-" + suffix + "-" + relative.replace("/", "-") )
            source_path.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n"
                                           for row in content), encoding="utf-8")
            capture_sources[relative] = source_path
        path = ROOT / ("diagnostic-" + suffix + ".json")
        write(path, spec)
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": "diagnostic-input.json",
                               "source": str(path.relative_to(REPO)), "sha256": checksum}] +
                             [{"path": relative, "source": str(source.relative_to(REPO)),
                               "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
                              for relative, source in capture_sources.items()],
                  "generator": {"source": str(path.relative_to(REPO)), "sha256": checksum}}
        write(ROOT / ("diagnostic-" + suffix + "-recipe.json"), recipe)
        print(suffix, path.stat().st_size)


if __name__ == "__main__":
    main()
