"""Bounded synthetic original-shaped sources for CPU tests only."""
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def body(x, y):
    return [[x, y, 0], [x+1, y, 0], [x+1, y+1, 0], [x, y+1, 0]]


def write(root, phase):
    root = Path(root)
    (root / "map.xodr").write_text("<OpenDRIVE>CPU fixture</OpenDRIVE>\n")
    bus_body = body(0, 3)
    site = {"format": "worker-transit-stop-site", "cell_id": "C394554",
            "layout": "road", "control": "bus_stop",
            "map_source": {"path": "map.xodr", "sha256": sha(root / "map.xodr")},
            "road": {"road_id": 9, "lane_source": "CPU fixture waypoint"},
            "stop": {"actor_id": 30, "blueprint_id": "static.prop.busstop",
                     "position_m": [0, 6, 0], "position_source": "CPU fixture transform"},
            "bus": {"actor_id": 40, "blueprint_id": "vehicle.mitsubishi.fusorosa",
                    "position_m": [1, 4.5, 0], "body_vertices_m": bus_body,
                    "door_side_source": "CPU bus-body proxy",
                    "door_region_source": "CPU bus-body proxy, actual door unverified",
                    "door_region_m": {"x_min": 0, "x_max": 1, "y_min": 4, "y_max": 4.5}},
            "diagnostic_only": True}
    (root / "transit-site.json").write_text(json.dumps(site) + "\n")
    history, trace, mapping = [], [], []
    for i in range(9):
        frame, time_s = 100+i, i*0.05
        pedestrian = body(0, 5-0.1*i if phase == "boarding_bus" else 5)
        history.append({"frame": frame, "time_s": time_s,
            "ego_body_vertices_m": body(-12+i, 0), "pedestrian_body_vertices_m": pedestrian,
            "bus_body_vertices_m": bus_body, "bus_actor_id": 40, "stop_actor_id": 30,
            "ego_class": "motor_vehicle", "pedestrian_class": "pedestrian",
            "ego_class_source": "CPU fixture blueprint", "pedestrian_class_source": "CPU fixture blueprint",
            "driver_control_source": "CPU fixture scripted input",
            "driver_observation_event": {"source": "original_driver_input", "observed": True} if i >= 2 else None,
            "ego_speed_mps": 4, "ego_brake": int(i>=2), "passenger_phase": phase,
            "contact_event": False,
            "pedestrian_stop_distance_m": (0.25 + (5.5-0.1*i-6 if phase == "boarding_bus" else -0.5)**2)**0.5,
            "pedestrian_bus_door_region_gap_m": max(pedestrian[0][1]-4.5,0)})
        trace.append({"frame": frame, "time_s": time_s, "position_m": [-12+i, 0, 0]})
        mapping.append({"video_frame": i, "carla_frame": frame, "time_s": time_s})
    for name, entries in (("encounter-history.jsonl", history), ("trace.jsonl", trace),
                          ("video_frames.jsonl", mapping)):
        (root / name).write_text("".join(json.dumps(row) + "\n" for row in entries))
    required = ("map.xodr", "transit-site.json", "encounter-history.jsonl", "video_frames.jsonl")
    (root / "acquisition.json").write_text(json.dumps({name: {"kind": "original_native", "sha256": sha(root / name)}
                                                     for name in required}) + "\n")
