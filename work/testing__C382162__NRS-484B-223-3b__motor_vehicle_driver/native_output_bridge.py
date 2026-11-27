"""Publish restored original center-lane packets to the pinned Native layout."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import subprocess

from native_capture import ASSIGNMENT, VIEWS


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, separators=(",", ":"), allow_nan=False)
        stream.write("\n")


def jsonl(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        for value in values:
            stream.write(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")


def encode(root, frames, view):
    target = root / (view + ".mkv")
    if target.exists():
        raise ValueError("original video already exists")
    command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
               "-f", "image2pipe", "-framerate", "20", "-vcodec", "png", "-i", "-",
               "-an", "-c:v", "ffv1", "-threads", "1", str(target)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for frame in frames:
            source = frame["camera_sources"][view]
            path = root / source["path"]
            if path.is_symlink() or not path.is_file() or sha(path) != source["sha256"]:
                raise ValueError("original camera source differs from sealed frame map")
            process.stdin.write(path.read_bytes())
        process.stdin.close()
        error = process.stderr.read()
        if process.wait(timeout=300) != 0:
            raise ValueError("original RGB encode failed: " + error.decode(errors="replace")[-300:])
    except Exception:
        process.kill()
        process.wait()
        raise
    finally:
        process.stderr.close()


def publish(attempt_root, *, map_bytes, restored):
    if restored is not True or type(map_bytes) is not bytes or not map_bytes:
        raise ValueError("restored Native world and original map bytes required")
    root = Path(attempt_root).resolve()
    inventory_path = root / "native/inventory.json"
    inventory = json.loads(inventory_path.read_text())
    if (not inventory["case_id"].startswith(ASSIGNMENT + "__") or
            inventory.get("source_kind") != "original_native" or
            inventory.get("frame_count") != 900 or
            inventory.get("camera_views") != list(VIEWS)):
        raise ValueError("exact 900-frame four-camera Native inventory incomplete")
    refs = inventory.get("sources", {})
    for name, relative in (("site", "native/site.json"), ("history", "native/history.json"),
                           ("frame_map", "native/frame-map.json")):
        ref = refs.get(name, {})
        if ref.get("path") != relative or ref.get("sha256") != sha(root / relative):
            raise ValueError("sealed original source mismatch: " + name)
    site = json.loads((root / "native/site.json").read_text())
    history = json.loads((root / "native/history.json").read_text())
    mapping = json.loads((root / "native/frame-map.json").read_text())
    if len(history) != 900 or len(mapping) != 900:
        raise ValueError("original center-lane frame count incomplete")
    map_record = json.loads((root / site["native_map_source"]["path"]).read_text())
    if map_record.get("opendrive_sha256") != hashlib.sha256(map_bytes).hexdigest():
        raise ValueError("original Native map differs from reviewed source")
    road = root / "road.xodr"
    road.write_bytes(map_bytes)
    from traffic_spec_adapter.adapter import write_adapter_graph
    from worker_exchange.native_output import seal_capture
    import networkx as nx

    try:
        actor_id = int(history[0]["actor_id"])
    except (TypeError, ValueError):
        raise ValueError("original actor ID invalid") from None
    trace, video_map, evidence, native = [], [], [], []
    for index, (row, source) in enumerate(zip(history, mapping)):
        number = row["original_frame"]
        if (source["original_frame"] != number or
                abs(source["time_s"] - row["time_s"]) > .005 or
                (index and number != history[index - 1]["original_frame"] + 1) or
                row["actor_id"] != actor_id):
            raise ValueError("original actor/frame join mismatch")
        position = [row["x"], row["y"], row["z"]]
        heading = math.degrees(math.atan2(row["heading_y"], row["heading_x"]))
        velocity = [row["speed_mps"] * row["heading_x"],
                    row["speed_mps"] * row["heading_y"], 0.0]
        participant = {"actor_id": actor_id, "blueprint": row["vehicle_blueprint"],
                       "blueprint_attributes": {"base_type": "car"},
                       "position_m": position, "body_vertices_m": row["body_vertices_m"],
                       "heading_deg": heading, "velocity_mps": velocity,
                       "speed_mps": row["speed_mps"]}
        packet = {"frame": number, "time_s": row["time_s"],
                  "participants": [participant],
                  "world_settings": {"no_rendering_mode": False},
                  "rgb_sensors": [{"view": view, "source": "original_native_callback_rgb"}
                                  for view in VIEWS],
                  "center_lane_observation": {
                      "road_id": row["road_id"], "lane_id": row["lane_id"],
                      "maneuver": row["maneuver"],
                      "route_source_sha256": refs["history"]["sha256"]}}
        graph = nx.DiGraph()
        graph.graph.update(frame=number, time_s=row["time_s"], observed_evidence=packet)
        graph_name = f"graphs/base/{number:08d}.adapter.json"
        graph_path = root / "capture/native" / graph_name
        graph_path.parent.mkdir(parents=True, exist_ok=True)
        write_adapter_graph(graph, graph_path)
        native.append({"frame": number, "simulation_time": row["time_s"],
                       "adapter_graph": graph_name})
        video_map.append({"video_frame": index, "carla_frame": number,
                          "native_frame": number, "time_s": row["time_s"]})
        trace.append({"frame": number, "time_s": row["time_s"],
                      "position": {"x": row["x"], "y": row["y"], "z": row["z"]},
                      "position_m": position, "velocity_mps": velocity,
                      "heading_deg": heading, "speed_mps": row["speed_mps"],
                      "control": {}})
        evidence.append({"actor_id": actor_id, "original_frame": number,
                         "replay_frame": number, "recording_time_s": row["time_s"],
                         "replay_simulation_time_s": row["time_s"],
                         "ego": {"body_vertices_m": row["body_vertices_m"],
                                 "position_m": position, "heading_deg": heading,
                                 "speed_mps": row["speed_mps"],
                                 "speed_provenance": "original_native_actor_readback"},
                         "original_observations": packet, "world": {"weather": {}}})
    jsonl(root / "trace.jsonl", trace)
    jsonl(root / "video_frames.jsonl", video_map)
    jsonl(root / "capture/evidence.jsonl", evidence)
    jsonl(root / "capture/native/frames.jsonl", native)
    (root / "capture/recorder_info.txt").write_text("Original Native center-lane capture\n")
    write(root / "capture/manifest.json", {
        "acquisition": "original_live_run", "diagnostic_fixture": False,
        "extraction_confirmed": True, "frames": 900,
        "observation_contract_version": 2,
        "sources": {"road.xodr": sha(road), "trace.jsonl": sha(root / "trace.jsonl")},
        "scope": "original center-lane route, body geometry and four RGB callbacks"})
    for view in VIEWS:
        encode(root, mapping, view)
    write(root / "acquisition-provenance.json", {
        "provenance_kind": "native", "diagnostic_fixture": False,
        "physical_acceptance_claimed": False})
    return seal_capture(root, frames=900, restoration={"restored": True}, errors=[],
                        encoder_exit_codes={view: 0 for view in VIEWS},
                        context={"map_sha256": sha(road),
                                 "route_sha256": refs["history"]["sha256"],
                                 "physical_acceptance_claimed": False})
