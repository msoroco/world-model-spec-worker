"""Build explicitly synthetic original-shaped emergency-lane CPU fixtures."""
import hashlib
import json
from pathlib import Path

from road_geometry import road_xml
from source_review import SOURCES


HERE = Path(__file__).resolve().parent
AID = HERE.name
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def wire(value):
    return json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n"


def lines(values):
    return "".join(wire(v) for v in values)


def make(index):
    suffix = f"probe_0{index}"
    case = AID + "__" + suffix
    directory = HERE / "cases" / suffix
    road = road_xml() + "\n"
    (directory / "road.xodr").write_text(road)
    context = {name: "Synthetic C405647 CPU diagnostic " + name +
               "; not original authority, visibility, safety or direction.\n"
               for name in SOURCES}
    refs = {name: {"path": "source_context/" + name + ".txt",
                   "sha256": digest(context[name].encode())} for name in SOURCES}
    review = {"assignment_id": AID, "case_id": case,
              "review_kind": "synthetic_diagnostic", "sources": refs,
              "qualification_role": "official_regulatory" if index == 3 else "authorized_emergency",
              "physical_acceptance_claimed": False, "legal_verdict": None}
    fmap, trace, capture_trace, evidence, graph_index, graphs = [], [], [], [], [], []
    lamps, signals = [], []
    for i in range(600):
        native = 1000 + i
        t = i / 20
        ego_speed = 6 if index == 2 else 4
        ego_x = -85 + ego_speed * t
        em_x = -20 + (0 if index == 4 else .06 * i)
        ego_lane = -2
        ego_y = -4.55 if index == 2 else -5.95
        em_y = -1.75
        flashing = i // 10 % 2 == 0
        hand = index == 4 and 30 <= i < 500
        officer = index == 5 and 30 <= i < 500
        fmap.append({"video_frame": i, "native_frame": native, "carla_frame": native,
                     "time_s": t, "camera_native_frames": dict.fromkeys(CAMERAS, native)})
        trace.append({"frame": i, "native_frame": native, "t_s": t,
                      "source_kind": "synthetic_native_sample",
                      "ego": {"actor_id": 1, "lane_id": ego_lane, "road_id": 405647,
                              "x_m": ego_x, "y_m": ego_y,
                              "half_width_m": .9, "half_length_m": 2,
                              "speed_mps": ego_speed,
                              "velocity_xyz_mps": [ego_speed, 0, 0]},
                      "emergency": {"actor_id": 2, "lane_id": -1, "road_id": 405647,
                                    "x_m": em_x, "y_m": em_y,
                                    "half_width_m": .9, "half_length_m": 2,
                                    "speed_mps": 0 if index == 4 else 1.2,
                                    "velocity_xyz_mps": [0 if index == 4 else 1.2, 0, 0]},
                      "traffic": None,
                      "weather_precipitation": 0,
                      "weather_wetness": 0,
                      "road_obstruction_observed": False,
                      "emergency_light_state": 1 if flashing else 0,
                      "source_driver_hand_signal_requested": index == 4,
                      "officer_hand_direction_requested": index == 5,
                      "requested_ego_speed_mps": ego_speed})
        lamps.append({"frame": i, "qualifying_flashes_visible": flashing,
                 "vehicle_visible": True})
        signals.append({"frame": i, "hand_signal_visible": hand,
                        "officer_direction_visible": officer,
                        "officer_direction": "proceed" if officer else "none"})
        body = [[ego_x + dx, ego_y + dy, z]
                for dx in (-2, 2) for dy in (-.8, .8) for z in (8, 9.5)]
        capture_trace.append({"frame": native, "time_s": t,
                              "position": {"x": ego_x, "y": ego_y, "z": 8.5},
                              "position_m": [ego_x, ego_y, 8.5], "heading_deg": 0,
                              "speed_mps": ego_speed, "speed_mph": ego_speed / .44704,
                              "velocity_mps": [ego_speed, 0, 0],
                              "control": {"throttle": .3, "brake": 0}})
        evidence.append({"original_frame": native, "replay_frame": native,
                         "actor_id": 1, "recording_time_s": t,
                         "replay_simulation_time_s": t,
                         "ego": {"position_m": [ego_x, ego_y, 8.5],
                                 "heading_deg": 0, "speed_mps": ego_speed,
                                 "body_vertices_m": body,
                                 "speed_provenance": "synthetic_native_sample",
                                 "synthetic_diagnostic": True},
                         "participants": {},
                         "world": {"weather": {"cloudiness": 0, "fog_density": 0,
                                               "precipitation": 0,
                                               "wetness": 0},
                                   "road_projection": {"road_id": 405647,
                                                       "lane_id": ego_lane,
                                                       "section_id": 0,
                                                       "s_m": ego_x + 120}}})
        graph_path = f"graphs/base/{native:08d}.adapter.json"
        graph_index.append({"frame": native, "simulation_time": t,
                            "base": graph_path, "adapter_graph": graph_path,
                            "nodes": 1, "edges": 0})
        graphs.append({"path": "capture/native/" + graph_path,
                       "attributes": {"frame": native, "simulation_time_s": t,
                                      "source": "synthetic C405647 emergency fixture",
                                      "synthetic_diagnostic": True},
                       "nodes": [{"id": "ego", "attributes": {
                           "entity_id": 1, "sem_class": "ego",
                           "vertex": [ego_x, ego_y, 8.5],
                           "forward": [1, 0, 0], "threedbbox": body}}],
                       "edges": []})
    capture_text = lines(capture_trace)
    files = {"emergency-review.json": wire(review),
             "video_frames.jsonl": lines(fmap),
             "emergency-native.jsonl": lines(trace),
             "lamp-pixel-review.json": wire({"case_id": case,
                 "review_kind": "synthetic_diagnostic", "frames": lamps}),
             "signal-pixel-review.json": wire({"case_id": case,
                 "review_kind": "synthetic_diagnostic", "frames": signals}),
             "trace.jsonl": capture_text,
             "capture/evidence.jsonl": lines(evidence),
             "capture/native/frames.jsonl": lines(graph_index),
             "capture/manifest.json": wire({"synthetic_diagnostic": True,
                "extraction_confirmed": True, "frames": 600,
                "sources": {"trace.jsonl": digest(capture_text.encode()),
                            "road.xodr": digest(road.encode())}}),
             "capture/recorder_info.txt": "Synthetic C405647 CPU diagnostic; no CARLA recorder\nCreate 1: vehicle.tesla.model3 (0)\n"}
    files.update({"source_context/" + name + ".txt": text
                  for name, text in context.items()})
    spec = {"files": files, "graphs": graphs,
            "videos": [{"path": name + ".mkv", "frames": 600,
                        "width": 1920 if name == "overview" else 1280,
                        "height": 1080 if name == "overview" else 720,
                        "fps": 20, "color": color}
                       for name, color in zip(CAMERAS,
                                               ("blue", "green", "white", "red"))]}
    spec_path = directory / "fixture-spec.json"
    spec_path.write_text(json.dumps(spec, separators=(",", ":")) + "\n")
    recipe = {"format": "worker-fixture-recipe",
              "sources": [{"path": "road.xodr",
                           "source": "work/" + AID + "/cases/" + suffix + "/road.xodr",
                           "sha256": digest(road.encode())}],
              "generator": {"source": "work/" + AID + "/cases/" + suffix + "/fixture-spec.json",
                            "sha256": digest(spec_path.read_bytes())}}
    (directory / "fixture-recipe.json").write_text(json.dumps(recipe, indent=2) + "\n")
    return {"case": case, "spec_bytes": spec_path.stat().st_size}


if __name__ == "__main__":
    print(json.dumps([make(i) for i in range(1, 6)]))
