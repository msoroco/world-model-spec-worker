"""Seal a restored two-vehicle Native signal capture for the pinned runtime."""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path

import native_signal as signal


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, separators=(",", ":"), allow_nan=False)
        stream.write("\n")


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False) + "\n")


def encode(root, rows, view):
    target = root / (view + ".mkv")
    signal.require(not target.exists(), "original video output exists")
    command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
               "-f", "image2pipe", "-framerate", "20", "-vcodec", "png",
               "-i", "-", "-an", "-c:v", "ffv1", "-threads", "1", str(target)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    try:
        for row in rows:
            path = root / "cameras" / view / f'{row["source_frame_id"]:06d}.png'
            signal.require(path.is_file() and not path.is_symlink(),
                           "original synchronized RGB image missing")
            process.stdin.write(path.read_bytes())
        process.stdin.close()
        error = process.stderr.read()
        signal.require(process.wait(timeout=300) == 0,
                       "original RGB encode failed: " +
                       error.decode(errors="replace")[-300:])
    except Exception:
        process.kill()
        process.wait()
        raise
    finally:
        process.stderr.close()


def participant(row):
    try:
        actor_id = int(row["actor_id"])
    except (TypeError, ValueError):
        raise ValueError("original Native actor ID invalid") from None
    blueprint = row["vehicle_blueprint"]
    signal.require(isinstance(blueprint, str) and blueprint.startswith("vehicle."),
                   "original motor vehicle blueprint missing")
    position = [row["x"], row["y"], row["z"]]
    heading = math.degrees(math.atan2(row["heading_y"], row["heading_x"]))
    velocity = [row["speed_mps"] * row["heading_x"],
                row["speed_mps"] * row["heading_y"], 0.0]
    return {"actor_id": actor_id, "blueprint": blueprint,
            "blueprint_attributes": {"base_type": "car"},
            "position_m": position, "body_vertices_m": row["body_vertices_m"],
            "heading_deg": heading, "velocity_mps": velocity,
            "speed_mps": row["speed_mps"]}


def publish(root, *, map_bytes, restored):
    signal.require(restored is True and type(map_bytes) is bytes and map_bytes,
                   "original Native restoration and OpenDRIVE bytes required")
    root = Path(root)
    inventory = json.loads((root / "inventory.json").read_text())
    refs = inventory.get("sources", {})
    names = (("site", "site.json"), ("ego_history", "ego-history.json"),
             ("other_history", "other-history.json"),
             ("frame_map", "frame-map.json"))
    signal.require(set(refs) == {name for name, _ in names} and
                   inventory.get("frame_count") == signal.FULL_FRAMES and
                   inventory.get("camera_views") == list(signal.VIEWS),
                   "sealed 900-frame two-vehicle Native source inventory incomplete")
    for name, filename in names:
        signal.require(refs[name].get("path") == filename and
                       refs[name].get("sha256") == sha(root / filename),
                       "sealed Native source mismatch: " + filename)
    site = json.loads((root / "site.json").read_text())
    ego = json.loads((root / "ego-history.json").read_text())
    other = json.loads((root / "other-history.json").read_text())
    frame_map = json.loads((root / "frame-map.json").read_text())
    signal.require(hashlib.sha256(map_bytes).hexdigest() == site.get("map_sha256"),
                   "loaded OpenDRIVE differs from sealed reviewed map")
    case_id = inventory["case_id"]
    case = next((item for item in signal.CASES
                 if case_id == signal.ASSIGNMENT + "__" + item.name), None)
    signal.require(case is not None, "unknown exact inoperative-signal case")
    # The external site packet path is available in the inventory only as a
    # hash. Source records were checked before CARLA import and in capture.
    signal.require(len(ego) == len(other) == len(frame_map) == signal.FULL_FRAMES,
                   "original Native histories incomplete")
    road = root / "road.xodr"
    signal.require(not road.exists(), "original OpenDRIVE output already exists")
    road.write_bytes(map_bytes)
    from traffic_spec_adapter.adapter import write_adapter_graph
    from worker_exchange.native_output import seal_capture
    import networkx as nx
    trace, mapping, evidence, native = [], [], [], []
    for index, (erow, orow, frame_ref) in enumerate(zip(ego, other, frame_map)):
        frame = erow["source_frame_id"]
        signal.require(type(frame) is int and frame == orow["source_frame_id"] and
                       frame_ref == {"frame_index": index, "native_frame": frame,
                                     "time_s": erow["time_s"]} and
                       (index == 0 or frame == ego[index - 1]["source_frame_id"] + 1),
                       "original signal frame-map join mismatch")
        participants = [participant(erow), participant(orow)]
        packet = {"frame": frame, "time_s": erow["time_s"],
                  "participants": participants,
                  "world_settings": {"no_rendering_mode": False},
                  "rgb_sensors": [{"view": view, "source": "original_native_callback_rgb"}
                                  for view in signal.VIEWS],
                  "inoperative_signal_observation": {
                      "signal_id": site["signal_id"],
                      "governed_approach": site["governed_approach"],
                      "signal_installed": erow["signal_installed"],
                      "vehicular_heads_uncovered": erow["signal_uncovered"],
                      "signal_operating": erow["signal_operating"],
                      "governing_head_operating": erow["governing_head_operating"],
                      "all_heads_wholly_inoperative": erow["all_heads_wholly_inoperative"],
                      "ego_front_station_m": erow["front_m"],
                      "other_front_station_m": orow["front_m"],
                      "other_within_intersection": orow["within_intersection"],
                      "other_cleared_conflict_zone": orow["cleared_conflict_zone"],
                      "physical_occluder_source_sha256": site["physical_occluder_source_sha256"],
                      "map_sha256": site["map_sha256"]}}
        graph = nx.DiGraph()
        graph.graph.update(frame=frame, time_s=erow["time_s"], observed_evidence=packet)
        graph_name = f"graphs/base/{frame:08d}.adapter.json"
        target = root / "capture/native" / graph_name
        target.parent.mkdir(parents=True, exist_ok=True)
        write_adapter_graph(graph, target)
        native.append({"frame": frame, "simulation_time": erow["time_s"],
                       "adapter_graph": graph_name})
        mapping.append({"video_frame": index, "carla_frame": frame,
                        "native_frame": frame, "time_s": erow["time_s"]})
        first = participants[0]
        trace.append({"frame": frame, "time_s": erow["time_s"],
                      "position": {"x": erow["x"], "y": erow["y"], "z": erow["z"]},
                      "position_m": first["position_m"],
                      "velocity_mps": first["velocity_mps"],
                      "heading_deg": first["heading_deg"],
                      "speed_mps": erow["speed_mps"], "control": {}})
        evidence.append({"actor_id": first["actor_id"], "original_frame": frame,
                         "replay_frame": frame, "recording_time_s": erow["time_s"],
                         "replay_simulation_time_s": erow["time_s"],
                         "ego": {"body_vertices_m": erow["body_vertices_m"],
                                 "position_m": first["position_m"],
                                 "heading_deg": first["heading_deg"],
                                 "speed_mps": erow["speed_mps"],
                                 "speed_provenance": "original_native_actor_readback"},
                         "original_observations": packet, "world": {"weather": {}}})
    write_jsonl(root / "trace.jsonl", trace)
    write_jsonl(root / "video_frames.jsonl", mapping)
    write_jsonl(root / "capture/evidence.jsonl", evidence)
    write_jsonl(root / "capture/native/frames.jsonl", native)
    (root / "capture/recorder_info.txt").write_text(
        "Original Native inoperative-signal capture\n")
    write_json(root / "capture/manifest.json", {
        "acquisition": "original_live_run", "diagnostic_fixture": False,
        "extraction_confirmed": True, "frames": signal.FULL_FRAMES,
        "observation_contract_version": 2,
        "sources": {"road.xodr": sha(road), "trace.jsonl": sha(root / "trace.jsonl")},
        "scope": "original signal state, two vehicles and four RGB callbacks"})
    for view in signal.VIEWS:
        encode(root, ego, view)
    write_json(root / "acquisition-provenance.json", {
        "provenance_kind": "native", "diagnostic_fixture": False,
        "physical_acceptance_claimed": False})
    return seal_capture(root, frames=signal.FULL_FRAMES,
                        restoration={"restored": True}, errors=[],
                        encoder_exit_codes={view: 0 for view in signal.VIEWS},
                        context={"map_sha256": sha(road),
                                 "site_sha256": inventory["reviewed_site_sha256"],
                                 "physical_acceptance_claimed": False})
