"""Build explicit synthetic saved-source recipes for all six C150041 cases.

Generated videos and telemetry test software only. They are never Native evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from parking_pose import REQUESTS


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def build(kind):
    if kind not in REQUESTS:
        raise ValueError("unknown exact saved-fixture case")
    directory = ROOT / "diagnostic" / kind
    construction = json.loads((directory / "construction.json").read_text())
    scene = json.loads(next(item["content"] for item in construction["files"]
                            if item["path"] == "scene.json"))
    packet = json.loads((directory / "reviewed-context.json").read_text())
    if scene["case_id"] != ASSIGNMENT + "__" + kind or packet["context"]["activity"] != REQUESTS[kind][0]:
        raise ValueError("saved fixture case or activity changed")
    pose = scene["target_pose"]
    history = []
    for i, speed in enumerate((2.0, 0.2, 0.1, 0.0, 0.0)):
        history.append({"frame": i + 1, "time_s": (i + 1) / 20,
                        "body_vertices_xy_m": pose["target_body_vertices_xy_m"],
                        "vehicle_forward_xy": pose["target_forward_xy"],
                        "speed_m_s": speed,
                        "control": {"throttle": 0.0, "steer": 0.0, "brake": 1.0}})
    lines = lambda rows: "".join(json.dumps(row, allow_nan=False) + "\n" for row in rows)
    mapping = [{"video_frame": i, "carla_frame": i + 1, "time_s": (i + 1) / 20}
               for i in range(len(history))]
    camera_map = [{"frame": i + 1, "time_s": (i + 1) / 20,
                   "camera_names": list(scene["capture_plan"]["cameras"]),
                   "source_path": "video_frames.jsonl"} for i in range(len(history))]
    trace = [{"frame": row["frame"], "time_s": row["time_s"],
              "position": {"x": sum(point[0] for point in row["body_vertices_xy_m"]) / 4,
                           "y": sum(point[1] for point in row["body_vertices_xy_m"]) / 4,
                           "z": 0.0},
              "heading_deg": math.degrees(math.atan2(row["vehicle_forward_xy"][1],
                                                    row["vehicle_forward_xy"][0])),
              "speed_mps": row["speed_m_s"]} for row in history]
    spec = {"files": {"parking-history.jsonl": lines(history),
                       "video_frames.jsonl": lines(mapping),
                       "camera-frame-map.jsonl": lines(camera_map),
                       "trace.jsonl": lines(trace)},
            "graphs": [],
            "videos": [{"path": name + ".mkv", "frames": len(history),
                        "width": 1920 if name == "overview" else 1280,
                        "height": 1080 if name == "overview" else 720,
                        "fps": 20, "color": "black"}
                       for name in scene["capture_plan"]["cameras"]]}
    spec_path = directory / "saved-fixture-spec.json"
    _write(spec_path, spec)
    sources = []
    for relative in ("reviewed-context.json", *(v["path"] for v in packet["sources"].values())):
        source = directory / relative
        sources.append({"path": relative, "source": source.relative_to(REPO).as_posix(),
                        "sha256": _sha(source)})
    recipe = {"format": "worker-fixture-recipe", "sources": sources,
              "generator": {"source": spec_path.relative_to(REPO).as_posix(),
                            "sha256": _sha(spec_path)}}
    recipe_path = directory / "saved-fixture-recipe.json"
    _write(recipe_path, recipe)
    return recipe_path


if __name__ == "__main__":
    for kind in REQUESTS:
        print(build(kind))
