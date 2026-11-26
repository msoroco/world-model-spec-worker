"""Generate source-shaped public CPU fixtures for the four exact pass cases."""

import hashlib
import json
from pathlib import Path
import sys

from scene import FRAMES, open_drive, target


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
REPO = PACKAGE.parents[1]
SUFFIXES = ("witness_1", "witness_2", "exception_1_1", "exception_1_2")
CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":"), ensure_ascii=False) + "\n")


def lines(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(value, separators=(",", ":")) for value in values) + "\n")


def body(x, y, length, width):
    return [[round(x + dx, 5), round(y + dy, 5), z]
            for dx in (-length / 2, length / 2)
            for dy in (-width / 2, width / 2) for z in (0, 1.8)]


def build(suffix):
    construction = json.loads((PACKAGE / "selected-native-draft" / suffix / "construction.json").read_text())
    config = json.loads(next(item["content"] for item in construction["files"]
                             if item["path"] == "config.json"))
    folder = PACKAGE / "diagnostic" / suffix
    sources = folder / "sources"
    (sources / "road.xodr").parent.mkdir(parents=True, exist_ok=True)
    (sources / "road.xodr").write_text(open_drive() + "\n")
    write(sources / "pass-context.json", {"case_id": config["case_id"],
          "statutory_subject": "bicycle", "source_kind": "generated_software_diagnostic",
          "left_lane_availability_verified": False, "reasonable_safety_judged": False})
    poses, traces, mapping, evidence, frames, graphs = [], [], [], [], [], []
    for index in range(FRAMES):
        planned = target(suffix, index)
        native_frame = 1000 + index
        time_s = round(index / 20, 5)
        ex, ey = planned.ego_x_m, planned.ego_y_m
        cx, cy = planned.cyclist_x_m, planned.cyclist_y_m
        ego = {"actor_id": 101, "blueprint_id": "vehicle.tesla.model3",
               "center_xy_m": [ex, ey], "body_xy_m": [p[:2] for p in body(ex, ey, 4.2, 1.8)[::2]],
               "heading_deg": 0, "speed_mps": 3}
        cyclist = {"actor_id": 202, "blueprint_id": "vehicle.bh.crossbike",
                   "center_xy_m": [cx, cy], "body_xy_m": [p[:2] for p in body(cx, cy, 1.2, .6)[::2]],
                   "heading_deg": 0, "speed_mps": 1.5}
        blocker = ({"actor_id": 303, "blueprint_id": "vehicle.audi.a2",
                    "center_xy_m": [planned.left_blocker_x_m, planned.left_blocker_y_m]}
                   if planned.left_blocker_x_m is not None else None)
        poses.append({"frame": native_frame, "video_frame": index, "time_s": time_s,
                      "ego": ego, "cyclist": cyclist, "left_blocker": blocker})
        traces.append({"frame": native_frame, "time_s": time_s,
                       "position": {"x": ex, "y": ey, "z": 1},
                       "position_m": [ex, ey, 1], "heading_deg": 0,
                       "speed_mps": 3, "speed_mph": 3 / .44704,
                       "velocity_mps": [3, 0, 0], "control": {"diagnostic": True}})
        mapping.append({"video_frame": index, "carla_frame": native_frame,
                        "native_frame": native_frame, "time_s": time_s,
                        "camera_native_frames": {name: native_frame for name, _, _ in CAMERAS}})
        evidence.append({"actor_id": 101,
            "ego": {"body_vertices_m": body(ex, ey, 4.2, 1.8),
                    "heading_deg": 0, "position_m": [ex, ey, 1],
                    "speed_mps": 3, "speed_provenance": "synthetic_native_sample",
                    "synthetic_diagnostic": True},
            "original_frame": native_frame,
            "other_actors": [{"actor_id": 202, "sem_class": "bicycle",
                              "body_vertices_m": body(cx, cy, 1.2, .6)}],
            "recording_time_s": time_s, "replay_frame": native_frame,
            "replay_simulation_time_s": time_s,
            "world": {"road_projection": {"lane_id": -1 if ey > -3.5 else -2,
                                           "road_id": 1, "s_m": ex + 100, "section_id": 0},
                      "weather": {"cloudiness": 0, "fog_density": 0,
                                  "precipitation": 0, "wetness": 0}}})
        relative = f"graphs/base/{index:08d}.adapter.json"
        frames.append({"adapter_graph": relative, "base": relative, "edges": 0,
                       "frame": native_frame, "nodes": 2, "simulation_time": time_s})
        graphs.append({"path": "capture/native/" + relative,
            "attributes": {"frame": native_frame, "simulation_time_s": time_s,
                           "source": "C247014 generated CPU diagnostic",
                           "synthetic_diagnostic": True}, "edges": [],
            "nodes": [{"id": "ego", "attributes": {"entity_id": 101,
                "forward": [1, 0, 0], "sem_class": "ego",
                "threedbbox": body(ex, ey, 4.2, 1.8), "vertex": [ex, ey, 1]}},
                {"id": "cyclist", "attributes": {"entity_id": 202,
                "forward": [1, 0, 0], "sem_class": "bicycle",
                "threedbbox": body(cx, cy, 1.2, .6), "vertex": [cx, cy, 1]}}]})
    for name, data in (("participant-poses.jsonl", poses), ("trace.jsonl", traces),
                       ("video_frames.jsonl", mapping), ("capture/evidence.jsonl", evidence)):
        lines(sources / name, data)
    write(sources / "capture/manifest.json", {"extraction_confirmed": True,
          "frames": FRAMES, "synthetic_diagnostic": True,
          "sources": {name: sha(sources / name) for name in
                      ("participant-poses.jsonl", "pass-context.json", "road.xodr", "trace.jsonl")}})
    spec = {"files": {"capture/native/frames.jsonl": "\n".join(
                json.dumps(row, separators=(",", ":")) for row in frames) + "\n",
                "capture/recorder_info.txt": "Synthetic diagnostic; no Native recording.\nCreate 101: vehicle.tesla.model3 (0)\n"},
            "graphs": graphs,
            "videos": [{"path": name + ".mkv", "frames": FRAMES,
                        "width": width, "height": height, "fps": 20, "color": "black"}
                       for name, width, height in CAMERAS]}
    write(folder / "fixture-spec.json", spec)
    recipe = {"format": "worker-fixture-recipe",
        "generator": {"source": str((folder / "fixture-spec.json").relative_to(REPO)),
                      "sha256": sha(folder / "fixture-spec.json")},
        "sources": [{"path": str(path.relative_to(sources)),
                     "source": str(path.relative_to(REPO)), "sha256": sha(path)}
                    for path in sorted(sources.rglob("*")) if path.is_file()]}
    write(folder / "fixture-recipe.json", recipe)
    return {"suffix": suffix, "recipe_sha256": sha(folder / "fixture-recipe.json"),
            "sources": len(recipe["sources"]), "frames": FRAMES}


if __name__ == "__main__":
    print(json.dumps([build(suffix) for suffix in SUFFIXES], sort_keys=True))
