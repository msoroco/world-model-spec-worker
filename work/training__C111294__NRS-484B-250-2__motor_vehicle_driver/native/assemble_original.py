"""Derive canonical saved inputs from retained Native source; no legal verdict."""
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def assemble(root, *, diagnostic=False):
    root = Path(root)
    actors = rows(root / "native-raw-actors.jsonl")
    frames = rows(root / "video_frames.jsonl")
    mapping = json.loads((root / "native-map-readback.json").read_text())
    report = json.loads((root / "native-capture-report.json").read_text())
    kind = "synthetic_fixture" if diagnostic else "original_native"
    if (len(actors) != 600 or len(frames) != 600 or
            mapping.get("source_kind") != kind or
            any(row.get("source_kind") != kind for row in actors) or
            report.get("error") is not None or
            report.get("observed_frames") != 600):
        raise ValueError("Original Native source and 600-frame capture required")
    for camera in ("overview", "approach", "reference_corner", "driver_reference", "raw"):
        if not (root / (camera + ".mkv")).is_file():
            raise ValueError("Missing retained camera or primary: " + camera)
    trace = []
    evidence = []
    native_frames = []
    history = []
    for index, (actor, frame) in enumerate(zip(actors, frames)):
        native = actor.get("native_frame")
        t = actor.get("time_s")
        if (actor.get("frame") != index or frame.get("video_frame") != index or
                frame.get("carla_frame") != native or frame.get("native_frame") != native or
                frame.get("time_s") != t):
            raise ValueError("Original actor/camera frame join failed")
        ego, other = actor["ego"], actor["other"]
        def participant(source):
            return {"actor_id": source["actor_id"], "center_xyz_m": source["center_native_xyz_m"],
                    "body_xyz_m": source["body_native_xyz_m"], "speed_mps": source["speed_mps"],
                    "velocity_xyz_mps": source["velocity_native_xyz_mps"],
                    "yaw_deg": source["yaw_deg"]}
        history.append({"frame": index, "native_frame": native, "time_s": t,
                        "ego": participant(ego), "other": participant(other),
                        "ego_road_id": actor.get("ego_road_id"),
                        "other_road_id": actor.get("other_road_id")})
        x, y, z = ego["center_native_xyz_m"]
        trace.append({"frame": index, "native_frame": native, "time_s": t,
                      "position": {"x": x, "y": y, "z": z}, "position_m": [x, y, z],
                      "heading_deg": ego["yaw_deg"], "speed_mps": ego["speed_mps"],
                      "speed_mph": ego["speed_mps"] * 2.2369362920544,
                      "velocity_mps": ego["velocity_native_xyz_mps"],
                      "control": actor.get("ego_control", {})})
        evidence.append({"original_frame": native, "recording_time_s": t,
                         "ego": {"body_vertices_m": ego["body_native_xyz_m"],
                                 "position_m": ego["center_native_xyz_m"],
                                 "heading_deg": ego["yaw_deg"], "speed_mps": ego["speed_mps"],
                                 "speed_provenance": "original_native_velocity"},
                         "other_actors": [{"actor_id": other["actor_id"],
                                           "body_vertices_m": other["body_native_xyz_m"],
                                           "position_m": other["center_native_xyz_m"]}],
                         "replay_frame": native, "replay_simulation_time_s": t,
                         "actor_id": ego["actor_id"],
                         "world": {"road_projection": {"road_id": actor.get("ego_road_id"),
                                                        "lane_id": -1}}})
        relative = f"graphs/base/{index:08d}.adapter.json"
        native_frames.append({"frame": native, "simulation_time": t,
                              "adapter_graph": relative, "base": relative,
                              "nodes": 2, "edges": 0})
        graph = {"attributes": {"frame": native, "simulation_time_s": t,
                                 "source_kind": kind},
                 "nodes": [{"id": "ego", "attributes": {"sem_class": "ego",
                            "entity_id": ego["actor_id"], "vertex": ego["center_native_xyz_m"],
                            "forward": [1.0, 0.0, 0.0],
                            "threedbbox": ego["body_native_xyz_m"]}},
                           {"id": "other", "attributes": {"sem_class": "vehicle",
                            "entity_id": other["actor_id"], "vertex": other["center_native_xyz_m"],
                            "forward": [0.0, 1.0, 0.0],
                            "threedbbox": other["body_native_xyz_m"]}}], "edges": []}
        put(root / "capture/native" / relative, graph)
    put(root / "actor-history.json", {"case_id": report["case_id"],
        "source_kind": kind, "synthetic": diagnostic, "rows": history,
        "source_sha256": sha(root / "native-raw-actors.jsonl")})
    put(root / "road-context.json", {"source_kind": kind,
        "ego_highway_roads": [250, 251, 252], "other_highway_roads": [253, 254, 255],
        "ego_entry_boundary_x_m": -20, "other_entry_boundary_y_m": -20,
        "native_map_readback_sha256": sha(root / "native-map-readback.json"),
        "public_highway_status_verified": False,
        "official_device_governance_verified": False,
        "opposite_direction_left_turn_exclusion_resolved": False,
        "subsection_4_exception_resolved": False})
    for name, output in (("trace.jsonl", trace), ("capture/evidence.jsonl", evidence),
                         ("capture/native/frames.jsonl", native_frames)):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n"
                                for row in output))
    (root / "capture/native/recorder_info.txt").write_text(
        f"{kind} actor source; no recorder claim\nCreate {actors[0]['ego']['actor_id']}: "
        f"{actors[0]['ego']['blueprint']} (0)\nCreate {actors[0]['other']['actor_id']}: "
        f"{actors[0]['other']['blueprint']} (0)\n")
    put(root / "capture/manifest.json", {"extraction_confirmed": True,
        "frames": 600, "source_kind": kind, "diagnostic_fixture": diagnostic,
        "sources": {name: sha(root / name) for name in
                    ("native-raw-actors.jsonl", "video_frames.jsonl", "native-map-readback.json",
                     "road.xodr", "actor-history.json", "road-context.json", "trace.jsonl",
                     "capture/evidence.jsonl", "capture/native/frames.jsonl")}})
    return {"frames": 600, "source_kind": kind,
            "actor_history_sha256": sha(root / "actor-history.json"),
            "original_native_observed": not diagnostic, "accepted": False}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(assemble(args.capture_dir)))
