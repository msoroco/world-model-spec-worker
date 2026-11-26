"""Publish restored original crosswalk packets as a sealed Core capture."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import subprocess

from native_capture import FRAME_COUNT, VIEWS
import near_crosswalk as near
from native_capture import ASSIGNMENT


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, separators=(",", ":"), allow_nan=False)
        stream.write("\n")


def _jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")


def _encode(root, frames, view):
    target = root / (view + ".mkv")
    if target.exists():
        raise ValueError("original video output already exists")
    command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
               "-f", "image2pipe", "-framerate", "20", "-vcodec", "png", "-i", "-",
               "-an", "-c:v", "ffv1", "-threads", "1", str(target)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for row in frames:
            image = root / "cameras" / view / f'{row["source_frame_id"]:06d}.png'
            if image.is_symlink() or not image.is_file():
                raise ValueError("original synchronized RGB frame missing")
            process.stdin.write(image.read_bytes())
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


def publish(root, *, map_bytes, restored):
    if restored is not True or type(map_bytes) is not bytes or not map_bytes:
        raise ValueError("original Native restoration and OpenDRIVE bytes required")
    root = Path(root)
    inventory = json.loads((root / "inventory.json").read_text())
    refs = inventory.get("sources", {})
    if set(refs) != {"site", "history", "frame_map"} or inventory.get("frame_count") != FRAME_COUNT:
        raise ValueError("sealed 900-frame Native source inventory incomplete")
    for name, filename in (("site", "site.json"), ("history", "history.json"),
                           ("frame_map", "frame-map.json")):
        if refs[name].get("path") != filename or refs[name].get("sha256") != _sha(root / filename):
            raise ValueError("sealed Native packet source mismatch")
    site = json.loads((root / "site.json").read_text())
    frames = json.loads((root / "history.json").read_text())
    frame_map = json.loads((root / "frame-map.json").read_text())
    if site.get("map_sha256") != hashlib.sha256(map_bytes).hexdigest():
        raise ValueError("loaded OpenDRIVE source differs from sealed map")
    case_id = inventory["case_id"]
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("exact crosswalk case mismatch")
    case_key = case_id.removeprefix(ASSIGNMENT + "__")
    case = next((item for item in near.CASES if item.name == case_key), None)
    if case is None:
        raise ValueError("unknown crosswalk case")
    measured = near.measure_original(frames, site, case)
    if len(frames) != FRAME_COUNT or len(frame_map) != FRAME_COUNT:
        raise ValueError("original speed history frame count incomplete")
    road = root / "road.xodr"
    if road.exists():
        raise ValueError("original OpenDRIVE output already exists")
    road.write_bytes(map_bytes)
    from traffic_spec_adapter.adapter import write_adapter_graph
    from worker_exchange.native_output import seal_capture
    import networkx as nx
    trace, mapping, evidence, native = [], [], [], []
    try:
        actor_id = int(frames[0]["actor_id"])
    except (TypeError, ValueError):
        raise ValueError("original CARLA actor ID invalid") from None
    for index, row in enumerate(frames):
        number = row.get("source_frame_id")
        if type(number) is not int or (index and number != frames[index - 1]["source_frame_id"] + 1):
            raise ValueError("original Native frame identity gap")
        if frame_map[index] != {"frame_index": index, "native_frame": number,
                                "time_s": row["time_s"]}:
            raise ValueError("original frame-map join mismatch")
        position = [row["x"], row["y"], row["z"]]
        heading = math.degrees(math.atan2(row["heading_y"], row["heading_x"]))
        velocity = [row["speed_mps"] * row["heading_x"],
                    row["speed_mps"] * row["heading_y"], 0.0]
        blueprint = row.get("vehicle_blueprint")
        if not isinstance(blueprint, str) or not blueprint.startswith("vehicle."):
            raise ValueError("original motor vehicle blueprint missing")
        participant = {"actor_id": actor_id, "blueprint": blueprint,
                       "blueprint_attributes": {"base_type": "car"},
                       "position_m": position, "body_vertices_m": row["body_vertices_m"],
                       "heading_deg": heading, "velocity_mps": velocity,
                       "speed_mps": row["speed_mps"]}
        packet = {"frame": number, "time_s": row["time_s"],
                  "participants": [participant],
                  "world_settings": {"no_rendering_mode": False},
                  "rgb_sensors": [{"view": name, "source": "original_native_callback_rgb"} for name in VIEWS],
                  "near_crosswalk_observation": {"road_id": row["road_id"],
                      "lane_id": row["lane_id"], "vehicle_front_xy": row["vehicle_front_xy"],
                      "stop_sign_id": site["stop_sign_id"], "crosswalk_marked": case.marked,
                      "map_sha256": site["map_sha256"]}}
        graph = nx.DiGraph()
        graph.graph.update(frame=number, time_s=row["time_s"], observed_evidence=packet)
        graph_name = f"graphs/base/{number:08d}.adapter.json"
        target = root / "capture/native" / graph_name
        target.parent.mkdir(parents=True, exist_ok=True)
        write_adapter_graph(graph, target)
        native.append({"frame": number, "simulation_time": row["time_s"],
                       "adapter_graph": graph_name})
        mapping.append({"video_frame": index, "carla_frame": number,
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
    _jsonl(root / "trace.jsonl", trace)
    _jsonl(root / "video_frames.jsonl", mapping)
    _jsonl(root / "capture/evidence.jsonl", evidence)
    _jsonl(root / "capture/native/frames.jsonl", native)
    (root / "capture/recorder_info.txt").write_text("Original Native near-side crosswalk capture\n")
    _write(root / "capture/manifest.json", {
        "acquisition": "original_live_run", "diagnostic_fixture": False,
        "extraction_confirmed": True, "frames": FRAME_COUNT,
        "observation_contract_version": 2,
        "sources": {"road.xodr": _sha(road), "trace.jsonl": _sha(root / "trace.jsonl")},
        "scope": "original crosswalk actor, front extent, sign and four RGB callbacks"})
    for view in VIEWS:
        _encode(root, frames, view)
    _write(root / "acquisition-provenance.json", {
        "provenance_kind": "native", "diagnostic_fixture": False,
        "physical_acceptance_claimed": False})
    return seal_capture(root, frames=FRAME_COUNT, restoration={"restored": True},
                        errors=[], encoder_exit_codes={view: 0 for view in VIEWS},
                        context={"map_sha256": _sha(road),
                                 "site_sha256": inventory["reviewed_site_sha256"],
                                 "physical_acceptance_claimed": False,
                                 "measured_crosswalk_entry_frame": measured["crosswalk_entry_frame"],
                                 "stopped_before_entry": measured["stopped_before_entry"]})
