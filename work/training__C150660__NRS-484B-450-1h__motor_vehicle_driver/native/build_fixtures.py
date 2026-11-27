"""Source-hashed synthetic diagnostics for every safety-zone request."""

import hashlib
import json
from pathlib import Path

from case_specs import CASES, target_x
from road import CURB_Y_M, ZONE_END_M, ZONE_NEAR_Y_M, ZONE_START_M, open_drive

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
REPO = HERE.parents[2]
FRAMES = 600
RATE = 20
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value if isinstance(value, str) else json.dumps(value, indent=2, sort_keys=True) + "\n")


def lines(rows):
    return "".join(json.dumps(row, separators=(",", ":"), sort_keys=True) + "\n" for row in rows)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def body_vertices(x, y):
    return [[x + dx, y + dy, z] for dx in (-2.25, 2.25)
            for dy in (-.9, .9) for z in (0, 1.5)]


def make(suffix):
    position, activity, exception, gap_ft = CASES[suffix]
    case = FOLDER.name + "__" + suffix
    root = HERE / "diagnostic" / suffix
    sources = root / "sources"
    x = target_x(suffix)
    y = CURB_Y_M + .9 + .1
    footprint = [[x + dx, y + dy] for dx in (-2.25, 2.25) for dy in (-.9, .9)]
    frame_map, trace, evidence, raw_frames, native_frames, graphs = [], [], [], [], [], []
    for index in range(FRAMES):
        t = round(index / RATE, 6)
        frame_map.append({"video_frame": index, "native_frame": index,
                          "carla_frame": index, "time_s": t,
                          "camera_native_frames": {name: index for name in CAMERAS}})
        raw_frames.append({"frame": index, "time_s": t, "native_frame": index,
                           "vehicle_stopped": True, "speed_mps": 0,
                           "stop_state_source": "synthetic_native_sample",
                           "vehicle_footprint_corners_m": footprint,
                           "vehicle_actor_id": 10, "requested_position": position})
        trace.append({"frame": index, "time_s": t,
                      "position_m": [x, y, .5], "position": {"x": x, "y": y, "z": .5},
                      "velocity_mps": [0, 0, 0], "speed_mps": 0, "speed_mph": 0,
                      "heading_deg": 0, "control": {"throttle": 0, "brake": 1,
                                                    "hand_brake": activity in ("stand", "park")}})
        evidence.append({"actor_id": 10, "original_frame": index,
                         "replay_frame": index, "recording_time_s": t,
                         "replay_simulation_time_s": t,
                         "ego": {"position_m": [x, y, .5],
                                 "body_vertices_m": body_vertices(x, y),
                                 "heading_deg": 0, "speed_mps": 0,
                                 "speed_provenance": "synthetic_native_sample",
                                 "synthetic_diagnostic": True},
                         "other_actors": [],
                         "world": {"road_projection": {"road_id": 1, "lane_id": -1,
                                                        "section_id": 0, "s_m": x},
                                   "weather": {"cloudiness": 0, "fog_density": 0,
                                               "precipitation": 0, "wetness": 0}}})
        graph_path = f"capture/native/graphs/base/{index:08d}.adapter.json"
        native_frames.append({"frame": index, "simulation_time": t,
                              "adapter_graph": f"graphs/base/{index:08d}.adapter.json",
                              "base": f"graphs/base/{index:08d}.adapter.json",
                              "nodes": 1, "edges": 0})
        graphs.append({"path": graph_path,
                       "attributes": {"frame": index, "simulation_time_s": t,
                                      "source": "C150660 safety-zone CPU diagnostic",
                                      "synthetic_diagnostic": True},
                       "nodes": [{"id": "ego", "attributes": {"entity_id": 10,
                                                           "sem_class": "ego",
                                                           "vertex": [x, y, .5],
                                                           "forward": [1, 0, 0],
                                                           "threedbbox": body_vertices(x, y)}}],
                       "edges": []})
    survey = {"case_id": case, "review_kind": "synthetic_diagnostic",
              "safety_zone_official_status": None, "zone_marker_readback": None,
              "adjacent_curb_readback": None, "halt_purpose": "synthetic " + activity + " request",
              "traffic_conflict": None, "applicable_law_direction": None,
              "officer_direction": None, "device_direction": None,
              "actual_pixels_reviewed": None, "independent_reviewer": None}
    raw = {"case_id": case, "source_kind": "synthetic_diagnostic",
           "zone": {"x_start_m": ZONE_START_M, "x_end_m": ZONE_END_M,
                    "curb_y_m": CURB_Y_M, "zone_near_y_m": ZONE_NEAR_Y_M,
                    "zone_map_source": "synthetic authored road",
                    "curb_map_source": "synthetic shoulder edge"},
           "construction_request": {"position": position, "activity": activity,
                                    "exception": exception, "gap_ft": gap_ft,
                                    "target_center_x_m": x, "context_requests": []},
           "frames": raw_frames}
    for name, value in {
        "zone_raw.json": raw, "context-survey.json": survey,
        "video_frames.jsonl": lines(frame_map), "trace.jsonl": lines(trace),
        "capture/evidence.jsonl": lines(evidence),
        "road.xodr": open_drive() + "\n",
        "authored-road.xodr": open_drive() + "\n",
    }.items():
        write(sources / name, value)
    write(sources / "capture/manifest.json", {
        "extraction_confirmed": True, "frames": FRAMES,
        "synthetic_diagnostic": True,
        "sources": {"road.xodr": sha(sources / "road.xodr"),
                    "trace.jsonl": sha(sources / "trace.jsonl")}})
    spec = {
        "files": {"capture/native/frames.jsonl": lines(native_frames),
                  "capture/recorder_info.txt": "Synthetic CPU diagnostic; no Native recording or physical acceptance.\nCreate 10: vehicle.tesla.model3 (0)\n"},
        "graphs": graphs,
        "videos": [{"path": name + ".mkv", "frames": FRAMES,
                    "width": 1920 if name == "overview" else 1280,
                    "height": 1080 if name == "overview" else 720,
                    "fps": RATE, "color": "black"} for name in CAMERAS],
    }
    spec_path = root / "fixture-spec.json"
    write(spec_path, spec)
    recipe = {"format": "worker-fixture-recipe",
              "generator": {"source": str(spec_path.relative_to(REPO)),
                            "sha256": sha(spec_path)},
              "sources": [{"path": str(path.relative_to(sources)),
                           "source": str(path.relative_to(REPO)), "sha256": sha(path)}
                          for path in sorted(sources.rglob("*")) if path.is_file()]}
    write(root / "fixture-recipe.json", recipe)
    return {"case_id": case, "recipe_sha256": sha(root / "fixture-recipe.json"),
            "source_files": len(recipe["sources"])}


if __name__ == "__main__":
    print(json.dumps([make(suffix) for suffix in CASES]))
