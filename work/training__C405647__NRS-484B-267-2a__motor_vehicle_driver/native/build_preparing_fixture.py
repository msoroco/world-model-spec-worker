"""Build text-inventoried synthetic preparing-branch diagnostics."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent
REPO = ASSIGNMENT.parents[1]
BASE = ASSIGNMENT.name + "__preparing_to_move__"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":"), ensure_ascii=False) + "\n")


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n"
                            for row in rows))


def build(branch, *, start_frame=120, suffix=""):
    case = BASE + branch
    root = ASSIGNMENT / "preparing-fixture-sources" / (branch + suffix)
    root.mkdir(parents=True, exist_ok=True)
    observations, mapping, trace, evidence, native, graphs = [], [], [], [], [], []
    ego_x, other_x = -100.0, 100.1
    for i in range(600):
        time_s, frame = i / 20, 3000 + i
        ego_speed = 14.0 if i < 160 else max(7.0, 14.0 - .175 * (i - 160))
        ego_x += ego_speed / 20
        other_speed = 1.0 if branch == "visible_vehicle_movement" and i >= start_frame else 0.0
        other_x += other_speed / 20
        lamp = (i // 10) % 2 == 0
        observation = {"case_id": case, "source_kind": "synthetic_cpu_fixture",
                       "video_frame": i, "native_frame": frame, "time_s": time_s,
                       "ego": {"actor_id": 107, "road_x_m": round(ego_x, 6),
                               "speed_mps": ego_speed},
                       "qualifying_vehicle": {"actor_id": 108,
                                              "road_x_m": round(other_x, 6), "speed_mps": other_speed,
                                              "kind": "authorized_emergency_vehicle",
                                              "authorized_source_id": "synthetic-authorization",
                                              "flashing_state": lamp,
                                              "lamp_equipment_source_id": "synthetic-equipment",
                                              "lamp_qualification_source_id": "synthetic-qualification"},
                       "officer_direction": None, "officer_direction_source_id": "synthetic-scene",
                       "road_context_source_id": "synthetic-road", "weather_context_source_id": "synthetic-weather",
                       "posted_limit_mps": 15, "wet_road": False, "visibility_m": 200,
                       "already_moving": False,
                       "visible_vehicle_movement": branch == "visible_vehicle_movement" and i >= start_frame,
                       "visible_driver_hand_signal": False,
                       "hand_signal_pose_requested": branch == "visible_driver_hand_signal" and i >= start_frame,
                       "hand_signal_driver_actor_id": 109 if branch == "visible_driver_hand_signal"
                       and i >= start_frame else None,
                       "camera_frames": {name: frame for name in CAMERAS}}
        observations.append(observation)
        mapping.append({"video_frame": i, "carla_frame": frame, "native_frame": frame,
                        "time_s": time_s})
        trace.append({"frame": frame, "time_s": time_s,
                      "position": {"x": round(ego_x, 6), "y": -1.75, "z": .5},
                      "position_m": [round(ego_x, 6), -1.75, .5],
                      "heading_deg": 0, "speed_mps": ego_speed,
                      "speed_mph": ego_speed / .44704,
                      "velocity_mps": [ego_speed, 0, 0],
                      "control": {"throttle": .2, "brake": 0, "hand_brake": False}})
        ego_body = [[ego_x + dx, -1.75 + dy, z]
                    for dx in (-2, 2) for dy in (-1, 1) for z in (0, 1.5)]
        other_body = [[other_x + dx, 1.75 + dy, z]
                      for dx in (-2, 2) for dy in (-1, 1) for z in (0, 1.5)]
        evidence.append({"original_frame": frame, "replay_frame": frame,
                         "actor_id": 107, "recording_time_s": time_s,
                         "replay_simulation_time_s": time_s,
                         "ego": {"position_m": [round(ego_x, 6), -1.75, .5],
                                 "heading_deg": 0, "speed_mps": ego_speed,
                                 "speed_provenance": "synthetic_native_sample",
                                 "body_vertices_m": ego_body},
                         "world": {"weather": {"cloudiness": 0, "precipitation": 0,
                                               "wetness": 0, "fog_density": 0},
                                   "road_projection": {"road_id": 405647,
                                                       "section_id": 0, "lane_id": -1,
                                                       "s_m": ego_x + 120}}})
        label = f"{frame:08d}"
        graph_path = f"capture/native/graphs/base/{label}.adapter.json"
        graphs.append({"path": graph_path,
                       "attributes": {"frame": frame, "simulation_time_s": time_s,
                                      "synthetic_diagnostic": True},
                       "nodes": [
                           {"id": "ego", "attributes": {"sem_class": "ego", "entity_id": 107,
                                                       "vertex": [ego_x, -1.75, .5],
                                                       "forward": [1, 0, 0], "threedbbox": ego_body}},
                           {"id": "emergency", "attributes": {"sem_class": "vehicle",
                                                             "entity_id": 108,
                                                             "vertex": [other_x, 1.75, .5],
                                                             "forward": [1, 0, 0],
                                                             "threedbbox": other_body}}], "edges": []})
        native.append({"frame": frame, "simulation_time": time_s, "time_s": time_s,
                       "base": f"graphs/base/{label}.adapter.json",
                       "abstract": f"graphs/abstract/{label}.pkl",
                       "adapter_graph": f"graphs/base/{label}.adapter.json",
                       "synthetic_diagnostic": True})
    for name, rows in (("preparing_observations.jsonl", observations),
                       ("video_frames.jsonl", mapping), ("trace.jsonl", trace),
                       ("capture/evidence.jsonl", evidence),
                       ("capture/native/frames.jsonl", native)):
        write_rows(root / name, rows)
    road = ('<OpenDRIVE><header revMajor="1" revMinor="4" name="C405647-2a-synthetic-speed-diagnostic" '
            'version="1" north="10" south="-10" east="450" west="-150" vendor="worker" />'
            '<road id="405647" name="emergency_approach" length="600" junction="-1">'
            '<link /><planView><geometry s="0" x="-150" y="0" hdg="0" length="600"><line />'
            '</geometry></planView><elevationProfile><elevation s="0" a="0" b="0" c="0" d="0" />'
            '</elevationProfile><lanes><laneOffset s="0" a="0" b="0" c="0" d="0" />'
            '<laneSection s="0"><left><lane id="1" type="driving" level="false">'
            '<width sOffset="0" a="3.5" b="0" c="0" d="0" />'
            '<roadMark sOffset="0" type="broken" color="white" width="0.12" />'
            '</lane></left><center><lane id="0" type="none" level="false">'
            '<roadMark sOffset="0" type="solid" color="yellow" width="0.12" />'
            '</lane></center><right><lane id="-1" type="driving" level="false">'
            '<width sOffset="0" a="3.5" b="0" c="0" d="0" />'
            '<roadMark sOffset="0" type="broken" color="white" width="0.12" />'
            '</lane></right></laneSection></lanes><objects /><signals /></road></OpenDRIVE>')
    (root / "road.xodr").write_text(road + "\n")
    write_json(root / "capture/manifest.json", {
        "extraction_confirmed": True, "frames": 600, "acquisition": "synthetic_diagnostic",
        "observation_contract_version": 1, "required_observations": ["kin.position"],
        "sources": {"road.xodr": sha(root / "road.xodr"),
                    "trace.jsonl": sha(root / "trace.jsonl")},
        "synthetic_diagnostic": True})
    (root / "capture/recorder_info.txt").write_text("Create 107: vehicle.lincoln.mkz_2020\n")
    write_json(root / "acquisition-provenance.json", {
        "provenance_kind": "synthetic_local_diagnostic", "diagnostic_fixture": True,
        "native_executed": False})
    files = [{"path": path.relative_to(root).as_posix(),
              "source": path.relative_to(REPO).as_posix(), "sha256": sha(path)}
             for path in sorted(root.rglob("*")) if path.is_file()]
    spec = {"files": {}, "graphs": graphs,
            "videos": [{"path": name + ".mkv", "frames": 600,
                        "width": width, "height": height, "fps": 20, "color": color}
                       for name, width, height, color in
                       (("overview", 1920, 1080, "blue"),
                        ("approach", 1280, 720, "red"),
                        ("reference_corner", 1280, 720, "green"),
                        ("driver_reference", 1280, 720, "white"))]}
    spec_path = ASSIGNMENT / ("preparing-diagnostic-" + branch + suffix + ".json")
    write_json(spec_path, spec)
    recipe = {"format": "worker-fixture-recipe", "sources": files,
              "generator": {"source": spec_path.relative_to(REPO).as_posix(),
                            "sha256": sha(spec_path)}}
    recipe_path = ASSIGNMENT / ("preparing-recipe-" + branch + suffix + ".json")
    recipe_path.write_text(json.dumps(recipe, indent=2) + "\n")
    return {"case": case, "recipe": recipe_path.relative_to(REPO).as_posix(),
            "recipe_sha256": sha(recipe_path), "spec_sha256": sha(spec_path)}


if __name__ == "__main__":
    for branch in ("visible_vehicle_movement", "visible_driver_hand_signal"):
        print(json.dumps(build(branch), sort_keys=True))
        print(json.dumps(build(branch, start_frame=100, suffix="-fallback1"), sort_keys=True))
