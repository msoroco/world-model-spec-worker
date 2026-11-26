"""Project sealed original door packets and RGB callbacks into Core capture.

This bridge runs only after the Native world and owned actors have been restored.
The diagnostic fixture path never invokes it.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from door_measurement import _source
from native_capture import VIEWS, FRAME_COUNT


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, separators=(",", ":"), allow_nan=False)
        stream.write("\n")


def _jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")


def _body3(body: list) -> list:
    return [[float(point[0]), float(point[1]), 0.0] for point in body]


def _encode(root: Path, frames: list, view: str) -> None:
    target = root / (view + ".mkv")
    if target.exists():
        raise ValueError("original video output already exists")
    command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
               "-f", "image2pipe", "-framerate", "20", "-vcodec", "png", "-i", "-",
               "-an", "-c:v", "ffv1", "-threads", "1", str(target)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for row in frames:
            image = root / "cameras" / view / f'{row["frame"]:06d}.png'
            if image.is_symlink() or not image.is_file():
                raise ValueError("original RGB callback frame missing")
            process.stdin.write(image.read_bytes())
        process.stdin.close()
        error = process.stderr.read()
        if process.wait(timeout=300) != 0:
            raise ValueError("original RGB video encoding failed: " + error.decode(errors="replace")[-300:])
    except Exception:
        process.kill()
        process.wait()
        raise
    finally:
        process.stderr.close()


def publish(root: Path, *, map_bytes: bytes, restored: bool) -> dict:
    """Seal source-joined 900-frame Core capture after Native restoration."""
    if restored is not True or type(map_bytes) is not bytes or not map_bytes:
        raise ValueError("original Native restoration and map bytes required")
    root = Path(root)
    inventory = json.loads((root / "inventory.json").read_text())
    sources = {name: _source(root, ref) for name, ref in inventory["sources"].items()}
    frames = sources["frame_map"]["frames"]
    if len(frames) != FRAME_COUNT or inventory.get("frame_count") != FRAME_COUNT:
        raise ValueError("original 900-frame Native capture incomplete")
    geometry = sources["geometry"]
    if geometry.get("map_sha256") != hashlib.sha256(map_bytes).hexdigest():
        raise ValueError("original loaded map differs from source-sealed geometry")
    for name in ("door", "activity", "passing_vehicle"):
        if len(sources[name]["samples"]) != FRAME_COUNT:
            raise ValueError("original actor source count differs")
    road = root / "road.xodr"
    if road.exists():
        raise ValueError("original map already published")
    road.write_bytes(map_bytes)
    from traffic_spec_adapter.adapter import write_adapter_graph
    from worker_exchange.native_output import seal_capture
    import networkx as nx
    config = json.loads((root / "config.json").read_text())
    selected_id = int(geometry["selected_vehicle_id"])
    passing_id = int(geometry["passing_vehicle_id"])
    selected_blueprint = geometry["selected_vehicle_blueprint"]
    passing_blueprint = geometry["passing_vehicle_blueprint"]
    loading_blueprint = geometry["loading_actor_blueprint"]
    if not selected_blueprint.startswith("vehicle.") or not passing_blueprint.startswith("vehicle."):
        raise ValueError("original vehicle blueprints missing")
    trace, mapping, evidence, native = [], [], [], []
    prior_x = None
    for index, frame in enumerate(frames):
        number, time_s = frame["frame"], frame["time_s"]
        if type(number) is not int or (index and number != frames[index - 1]["frame"] + 1):
            raise ValueError("original Native frame identity gap")
        door = sources["door"]["samples"][index]
        activity = sources["activity"]["samples"][index]
        passing = sources["passing_vehicle"]["samples"][index]
        if any(row.get("frame") != number or row.get("time_s") != time_s for row in (door, activity, passing)):
            raise ValueError("original Native actor/frame join differs")
        selected_xy = [geometry["selected_vehicle_center_x_m"], geometry["selected_vehicle_center_y_m"]]
        selected_body = [[selected_xy[0] - geometry["selected_vehicle_length_m"] / 2, selected_xy[1] - geometry["selected_vehicle_width_m"] / 2],
                         [selected_xy[0] - geometry["selected_vehicle_length_m"] / 2, selected_xy[1] + geometry["selected_vehicle_width_m"] / 2],
                         [selected_xy[0] + geometry["selected_vehicle_length_m"] / 2, selected_xy[1] + geometry["selected_vehicle_width_m"] / 2],
                         [selected_xy[0] + geometry["selected_vehicle_length_m"] / 2, selected_xy[1] - geometry["selected_vehicle_width_m"] / 2]]
        speed = 0.0 if prior_x is None else (passing["center_x_m"] - prior_x) * 20
        prior_x = passing["center_x_m"]
        participants = [
            {"actor_id": selected_id, "blueprint": selected_blueprint,
             "blueprint_attributes": {"base_type": "car"}, "position_m": [*selected_xy, 0.0],
             "body_vertices_m": _body3(selected_body), "heading_deg": 0.0,
             "velocity_mps": [0.0, 0.0, 0.0], "speed_mps": 0.0},
            {"actor_id": passing_id, "blueprint": passing_blueprint,
             "blueprint_attributes": {"base_type": "car"},
             "position_m": [passing["center_x_m"], passing["center_y_m"], 0.0],
             "body_vertices_m": _body3(passing["body_xy_m"]), "heading_deg": 0.0,
             "velocity_mps": [speed, 0.0, 0.0], "speed_mps": abs(speed)},
            {"actor_id": int(activity["loading_actor_id"]), "blueprint": loading_blueprint,
             "blueprint_attributes": {"base_type": "pedestrian" if loading_blueprint.startswith("walker.") else "prop"},
             "body_vertices_m": _body3(activity["body_xy_m"]),
             "velocity_mps": [activity["speed_mps"], 0.0, 0.0],
             "speed_mps": activity["speed_mps"]}]
        packet = {"frame": number, "time_s": time_s, "participants": participants,
                  "world_settings": {"no_rendering_mode": False},
                  "rgb_sensors": [{"view": name, "source": "original_native_callback_rgb"} for name in VIEWS],
                  "door_observation": door, "loading_observation": activity,
                  "passing_observation": passing,
                  "map_context": {"source_map_sha256": _sha(road)}}
        graph = nx.DiGraph()
        graph.graph.update(frame=number, time_s=time_s, observed_evidence=packet)
        name = f"graphs/base/{number:08d}.adapter.json"
        target = root / "capture/native" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        write_adapter_graph(graph, target)
        native.append({"frame": number, "simulation_time": time_s, "adapter_graph": name})
        mapping.append({"video_frame": index, "carla_frame": number,
                        "native_frame": number, "time_s": time_s})
        trace.append({"frame": number, "time_s": time_s,
                      "position": {"x": selected_xy[0], "y": selected_xy[1], "z": 0.0},
                      "position_m": [*selected_xy, 0.0], "velocity_mps": [0.0, 0.0, 0.0],
                      "heading_deg": 0.0, "speed_mps": 0.0, "speed_mph": 0.0, "control": {}})
        evidence.append({"actor_id": selected_id, "original_frame": number,
                         "replay_frame": number, "recording_time_s": time_s,
                         "replay_simulation_time_s": time_s,
                         "ego": {"body_vertices_m": _body3(selected_body), "position_m": [*selected_xy, 0.0],
                                 "heading_deg": 0.0, "speed_mps": 0.0,
                                 "speed_provenance": "original_native_actor_readback"},
                         "original_observations": packet, "world": {"weather": {}}})
    _jsonl(root / "trace.jsonl", trace)
    _jsonl(root / "video_frames.jsonl", mapping)
    _jsonl(root / "capture/evidence.jsonl", evidence)
    _jsonl(root / "capture/native/frames.jsonl", native)
    (root / "capture/recorder_info.txt").write_text("Original Native door/loading source capture\n")
    _write(root / "capture/manifest.json", {
        "acquisition": "original_live_run", "diagnostic_fixture": False,
        "extraction_confirmed": True, "frames": FRAME_COUNT, "observation_contract_version": 2,
        "sources": {"road.xodr": _sha(road), "trace.jsonl": _sha(root / "trace.jsonl")},
        "scope": "original door, loading actor, passing vehicle and four RGB callbacks"})
    for view in VIEWS:
        _encode(root, frames, view)
    _write(root / "acquisition-provenance.json", {
        "provenance_kind": "native", "diagnostic_fixture": False,
        "physical_acceptance_claimed": False})
    return seal_capture(root, frames=FRAME_COUNT, restoration={"restored": True}, errors=[],
                        encoder_exit_codes={view: 0 for view in VIEWS},
                        context={"map_sha256": _sha(road), "survey_sha256": inventory["survey_sha256"],
                                 "physical_acceptance_claimed": False})
