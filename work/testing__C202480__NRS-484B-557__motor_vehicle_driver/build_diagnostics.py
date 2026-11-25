"""Make source-inventoried synthetic rail fixtures for CPU compatibility.

These files exercise software joins only. They are not Native observations.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def encode(value) -> str:
    return json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n"


def lines(rows) -> str:
    return "".join(encode(row) for row in rows)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def source(files: dict[str, str], name: str, value) -> dict:
    content = encode(value)
    files[name] = content
    return {"path": name, "sha256": digest(content)}


def main() -> None:
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.removeprefix(HERE.name + "__")
        construction = json.loads((HERE / entry["construction"]).read_text())
        config = json.loads(next(f["content"] for f in construction["files"]
                                 if f["path"] == "config.json"))
        case = config["case"]
        gap_m = case["planned_stop_body_gap_ft"] / 3.280839895013123
        rolling = case["stop_behavior"] == "rolling"
        conflict = case["departure_context"] == "crossing_conflict"
        files: dict[str, str] = {}
        samples = []
        motion = []
        footprint = []
        conflicts = []
        trace = []
        mapping = []
        evidence = []
        frame_rows = []
        graphs = []
        for index in range(900):
            if index < 100:
                front_y = gap_m + 10 * (100 - index) / 100
                speed = 2.0
            elif rolling:
                front_y = gap_m - .05 * (index - 100)
                speed = 1.0
            elif index <= 120:
                front_y = gap_m
                speed = 0.0
            else:
                front_y = gap_m - .05 * (index - 120)
                speed = 1.0
            corners = [[-.9, front_y], [.9, front_y],
                       [.9, front_y + 4], [-.9, front_y + 4]]
            frame = 1000 + index
            movement = {"frame": index, "source_frame": frame,
                        "elapsed_s": index / 20, "speed_mps": speed}
            body = {"frame": index, "source_frame": frame,
                    "body_corners_xy_m": corners}
            motion.append(movement)
            footprint.append(body)
            samples.append({**movement, "body_corners_xy_m": corners})
            if conflict:
                conflicts.append({"frame": index, "source_frame": frame,
                                  "speed_mps": 1.0,
                                  "body_corners_xy_m": [[2, 0], [4, 0],
                                                        [4, 2], [2, 2]]})
            trace.append({"frame": frame, "time_s": index / 20,
                          "position": {"x": 0, "y": front_y + 2, "z": 0},
                          "heading_deg": 270,
                          "position_m": [0, front_y + 2, 0],
                          "speed_mps": speed, "speed_mph": speed / .44704,
                          "velocity_mps": [0, -speed, 0],
                          "control": {"throttle": 0, "brake": 0}})
            mapping.append({"video_frame": index, "carla_frame": frame,
                            "native_frame": frame, "time_s": index / 20})
            evidence.append({"original_frame": frame, "replay_frame": index,
                             "actor_id": 7, "recording_time_s": index / 20,
                             "replay_simulation_time_s": index / 20,
                             "world": {"weather": {}},
                             "ego": {"position_m": [0, front_y + 2, 0],
                                     "heading_deg": 270,
                                     "speed_mps": speed,
                                     "body_vertices_m": [[x, y, z]
                                                         for x, y in corners
                                                         for z in (0, 1.5)],
                                     "speed_provenance": "synthetic_native_sample"},
                             "original_observations": {"frame": frame,
                                                       "time_s": index / 20,
                                                       "participants": [],
                                                       "map_context": {}}})
            frame_rows.append({"frame": index, "simulation_time": index / 20,
                               "adapter_graph": f"graphs/base/{index:08d}.adapter.json"})
            graphs.append({"path": f"capture/native/graphs/base/{index:08d}.adapter.json",
                           "attributes": {"frame": index, "time_s": index / 20,
                                          "observed_evidence": {"frame": frame,
                                                                "time_s": index / 20,
                                                                "participants": [],
                                                                "map_context": {}}},
                           "nodes": [], "edges": []})
        rails = [{"a": [-10, 0], "b": [10, 0]}]
        context = {"crossing_type": "highway_railroad_grade",
                   "designation_authority": "state_dot",
                   "device_type": "official_stop_sign",
                   "device_governs": "railroad_approach",
                   "actor": "motor_vehicle_driver"}
        bindings = {
            "native_crossing_geometry": source(files, "native-crossing-geometry.json",
                                               {"nearest_track_rails": rails}),
            "native_authority_record": source(files, "native-authority-record.json",
                                              {key: context[key] for key in
                                               ("crossing_type", "designation_authority")}),
            "native_stop_device": source(files, "native-stop-device.json",
                                         {key: context[key] for key in
                                          ("device_type", "device_governs")}),
            "native_ego_kinematics": source(files, "native-ego-kinematics.json", motion),
            "native_ego_footprint": source(files, "native-ego-footprint.json", footprint),
        }
        if conflict:
            bindings["native_conflict_history"] = source(
                files, "native-conflict-history.json", conflicts)
        packet = {"sources": bindings, "context": context,
                  "nearest_track_rails": rails, "samples": samples,
                  "conflict_actor_present": conflict}
        if conflict:
            packet["conflict_samples"] = conflicts
        files["rail-stop-packet.json"] = encode(packet)
        files["trace.jsonl"] = lines(trace)
        files["video_frames.jsonl"] = lines(mapping)
        files["acquisition-provenance.json"] = encode({
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True})
        files["capture/evidence.jsonl"] = lines(evidence)
        files["capture/native/frames.jsonl"] = lines(frame_rows)
        files["capture/recorder_info.txt"] = "Create 7: vehicle.tesla.model3 (diagnostic) at (0, 0, 0)\n"
        files["road.xodr"] = ("<?xml version='1.0' encoding='utf-8'?>"
                              "<OpenDRIVE><header revMajor='1' revMinor='4' name='C202480 synthetic diagnostic' "
                              "version='1' north='100' south='-100' east='20' west='-20'/>"
                              "<road id='1' name='diagnostic crossing approach' length='200' junction='-1'>"
                              "<planView><geometry s='0' x='0' y='100' hdg='-1.5707963267948966' "
                              "length='200'><line/></geometry></planView><lanes><laneSection s='0'>"
                              "<center><lane id='0' type='none' level='false'/></center>"
                              "<right><lane id='-1' type='driving' level='false'><width sOffset='0' "
                              "a='3.5' b='0' c='0' d='0'/></lane></right></laneSection></lanes>"
                              "</road></OpenDRIVE>\n")
        files["capture/manifest.json"] = encode({
            "status": "draft", "acquisition": "original_live_run",
            "case_id": case_id, "frames": 900, "extraction_confirmed": True,
            "complete_driving_lanes": False,
            "sources": {"trace.jsonl": digest(files["trace.jsonl"]),
                        "road.xodr": digest(files["road.xodr"])}})
        diagnostic = {"files": files, "graphs": graphs,
                      "videos": [{"path": camera["name"] + ".mkv", "frames": 900,
                                  "width": camera["width"], "height": camera["height"],
                                  "fps": 20, "color": "black"}
                                 for camera in config["cameras"]]}
        spec = HERE / ("diagnostic-" + suffix + ".json")
        spec.write_text(encode(diagnostic), encoding="utf-8")
        note = HERE / ("diagnostic-note-" + suffix + ".json")
        note.write_text(encode({"case_id": case_id,
                                "scope": "synthetic software diagnostic only"}))
        recipe = HERE / ("fixture-recipe-" + suffix + ".json")
        recipe.write_text(encode({"format": "worker-fixture-recipe",
                                  "sources": [{"path": note.name,
                                               "source": str(note.relative_to(REPO)),
                                               "sha256": digest(note.read_text())}],
                                  "generator": {"source": str(spec.relative_to(REPO)),
                                                "sha256": digest(spec.read_text())}}))
        entry["fixture_recipe"] = str(recipe.relative_to(REPO))
        print(suffix, "diagnostic recipe", flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
