"""Build small, explicitly synthetic diagnostic inputs for five exact cases.

The copied road is an unrelated CPU test map. These files prove only the
current runtime's measurement/conversion plumbing, never the C102642 site.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
KINDS = {"open_near_overlap": ("open", "left", .05),
         "open_near_clear": ("open", "left", 2.0),
         "open_far_side": ("open", "right", .05),
         "board_near": ("board", "left", .05),
         "alight_near": ("alight", "left", .05)}


def compact(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def lines(rows):
    return "".join(compact(row) + "\n" for row in rows)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    road = (HERE / "diagnostic-road.xodr").read_text()
    map_sha = hashlib.sha256(road.encode()).hexdigest()
    runtime_sha = sha(REPO / "runtime/SOURCE-MANIFEST.json")
    plan = json.loads((HERE / "case-plan.json").read_text())
    draft = json.loads((HERE / "execution-manifest.draft.json").read_text())
    draft["format"] = "worker-execution-manifest"
    draft["runtime_manifest_sha256"] = runtime_sha
    for kind, (act, side, gap) in KINDS.items():
        case_id = AID + "__" + kind
        case_root = HERE / "cases" / kind
        source_root = case_root / "diagnostic-sources"
        source_root.mkdir(parents=True, exist_ok=True)
        context = {"map_sha256": map_sha, "survey_sha256": "diagnostic-unrelated-site",
                   "loading_site_id": "diagnostic-only", "parked_vehicle_id": "7",
                   "driver_id": "9", "passing_vehicle_id": "8",
                   "traffic_route_id": "diagnostic-only",
                   "camera_contract_id": "four-camera-diagnostic"}
        frames = []
        for index in range(3):
            frame = index + 1
            frames.append({"frame_id": frame, "sim_time_s": index / 20,
                           "camera_frames": {view: frame for view in
                                             ("front", "rear", "left", "right")},
                           "camera_sha256": {view: "diagnostic-only" for view in
                                             ("front", "rear", "left", "right")},
                           "selected_driver_id": "9", "observed_act": act if index == 1 else "none",
                           "act_side": side if index == 1 else None,
                           "passing_center_xy": [float(index), 1.5 + gap],
                           "passing_speed_mps": 4.0,
                           "act_envelope_xy": [[0, 1], [1, 1]],
                           "passing_body_xy": [[0, 1 + gap], [1, 1 + gap]],
                           "passing_response": {"brake": .2, "acceleration_mps2": -.5}})
        native_trace = {"source_kind": "native_original", "diagnostic_fixture": True,
                        "case_id": case_id, "sample_rate_hz": 20,
                        "fixed_context": context, "parked_center_xy": [0, 0],
                        "parked_heading_xy": [1, 0], "frames": frames}
        trace_path = source_root / "native-trace.json"
        write(trace_path, native_trace)
        door_path = source_root / "door-source.json"
        write(door_path, {"case_id": case_id, "selected_act": act,
                          "selected_side": side, "source_trace_sha256": sha(trace_path),
                          "site_survey": {"map_sha256": map_sha,
                                          "loading_site_id": "diagnostic-only",
                                          "governing_zone_source": "synthetic-only"},
                          "diagnostic_fixture": True,
                          "scope": "synthetic measurement and conversion preflight only"})
        trace_rows, mappings, evidence, native_frames, graphs = [], [], [], [], []
        body = [[x, y, z] for x in (-.5, .5) for y in (-.5, .5) for z in (0, 1)]
        for index, row in enumerate(frames):
            frame, stamp = row["frame_id"], row["sim_time_s"]
            packet = {"frame": frame, "time_s": stamp, "participants": [],
                      "map_context": {"diagnostic_fixture": True}}
            graph_name = f"graphs/base/{frame:08d}.adapter.json"
            graphs.append({"path": "capture/native/" + graph_name,
                           "attributes": {"frame": frame, "time_s": stamp,
                                          "observed_evidence": packet},
                           "nodes": [], "edges": []})
            native_frames.append({"frame": frame, "simulation_time": stamp,
                                  "adapter_graph": graph_name})
            mappings.append({"video_frame": index, "carla_frame": frame,
                             "native_frame": frame, "time_s": stamp})
            trace_rows.append({"frame": frame, "time_s": stamp,
                               "position_m": [0, 0, 0],
                               "position": {"x": 0, "y": 0, "z": 0},
                               "heading_deg": 0, "speed_mps": 0,
                               "speed_mph": 0, "velocity_mps": [0, 0, 0],
                               "control": {}})
            evidence.append({"actor_id": 7, "original_frame": frame,
                             "replay_frame": frame, "recording_time_s": stamp,
                             "replay_simulation_time_s": stamp,
                             "ego": {"body_vertices_m": body, "position_m": [0, 0, 0],
                                     "heading_deg": 0, "speed_mps": 0,
                                     "speed_provenance": "synthetic_native_sample"},
                             "original_observations": packet,
                             "world": {"weather": {}}})
        trace_text = lines(trace_rows)
        files = {"road.xodr": road, "trace.jsonl": trace_text,
                 "video_frames.jsonl": lines(mappings),
                 "capture/evidence.jsonl": lines(evidence),
                 "capture/native/frames.jsonl": lines(native_frames),
                 "capture/recorder_info.txt":
                     "Create 7: vehicle.tesla.model3 (diagnostic) at (0, 0, 0)\n",
                 "acquisition-provenance.json": compact({
                     "diagnostic_fixture": True,
                     "provenance_kind": "synthetic_fixture"}) + "\n"}
        files["capture/manifest.json"] = compact({
            "acquisition": "synthetic_fixture", "diagnostic_fixture": True,
            "case_id": case_id, "extraction_confirmed": True,
            "frames": 3, "sources": {"road.xodr": map_sha,
                                      "trace.jsonl": hashlib.sha256(trace_text.encode()).hexdigest()}}) + "\n"
        videos = [{"path": name + ".mkv", "frames": 3, "width": width,
                   "height": height, "fps": 20, "color": "black"}
                  for name, width, height in (
                      ("overview", 1920, 1080), ("approach", 1280, 720),
                      ("reference_corner", 1280, 720),
                      ("driver_reference", 1280, 720))]
        spec = case_root / "diagnostic.json"
        spec.write_text(compact({"files": files, "graphs": graphs,
                                 "videos": videos}) + "\n")
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": p.name, "source": p.relative_to(REPO).as_posix(),
                               "sha256": sha(p)} for p in (door_path, trace_path)],
                  "generator": {"source": spec.relative_to(REPO).as_posix(),
                                "sha256": sha(spec)}}
        write(case_root / "fixture-recipe.json", recipe)
        methods = {0: ("observed_action", "measure_observed_action"),
                   1: ("observed_action", "measure_observed_action"),
                   2: ("observed_action", "measure_observed_action"),
                   3: ("closest_side", "measure_closest_side"),
                   4: ("moving_interaction", "measure_moving_interaction")}
        requirements = []
        for index, disposition in enumerate(plan["requirement_dispositions"]):
            if case_id not in disposition.get("case_ids", []):
                continue
            key, method = methods[index]
            requirements.append({"disposition_index": index,
                                 "requirement": disposition["requirement"],
                                 "source": disposition["source"],
                                 "output_key": key, "method": method,
                                 "value_type": "object", "kind": "measured",
                                 "inputs": ["door-source.json", "native-trace.json"]})
        write(case_root / "measurement-contract.json", {
            "format": "worker-measurement-contract", "assignment_id": AID,
            "case_id": case_id, "requirements": requirements,
            "negative": {"remove": ["door-source.json"],
                         "error_contains": "Missing required source: door-source.json"},
            "scope": "synthetic CPU contract; original Native source required for delivery"})
        selected = next(row for row in draft["cases"] if row["case_id"] == case_id)
        selected["measurement_contract"] = f"cases/{kind}/measurement-contract.json"
        selected["measurement_procedure"] = {"entrypoint": "analysis.py"}
        selected["fixture_recipe"] = f"work/{AID}/cases/{kind}/fixture-recipe.json"
        print(kind, "source bytes", trace_path.stat().st_size,
              "spec bytes", spec.stat().st_size, "runtime", runtime_sha[:12])
    write(HERE / "execution-manifest.cpu-draft.json", draft)


if __name__ == "__main__":
    build()
