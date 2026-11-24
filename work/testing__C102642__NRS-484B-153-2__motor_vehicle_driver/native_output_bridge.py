"""Publish original door-action frames into the current runtime capture format.

Only sealed Native observations and original RGB callbacks enter this bridge.
It does not infer legal interference or claim that an action was physically
visible to a later reviewer.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


VIEWS = {"front": "overview", "rear": "approach",
         "left": "reference_corner", "right": "driver_reference"}


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> None:
    if path.exists():
        raise ValueError("original output already exists: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    if path.exists():
        raise ValueError("original output already exists: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")


def encode_view(root: Path, rows: list[dict], view: str, target: str) -> None:
    output = root / (target + ".mkv")
    if output.exists():
        raise ValueError("original camera video already exists")
    command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
               "-f", "image2pipe", "-framerate", "20", "-vcodec", "png", "-i", "-",
               "-an", "-c:v", "ffv1", "-threads", "1", str(output)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for row in rows:
            path = root / "cameras" / view / f'{row["frame_id"]:06d}.png'
            source = path.read_bytes()
            if hashlib.sha256(source).hexdigest() != row["camera_sha256"][view]:
                raise ValueError("original camera bytes changed: " + view)
            process.stdin.write(source)
        process.stdin.close()
        error = process.stderr.read()
        if process.wait(timeout=300) != 0:
            raise ValueError("original camera encoding failed: " + error.decode(errors="replace")[-500:])
    except Exception:
        process.kill()
        process.wait()
        raise
    finally:
        process.stderr.close()


def publish(root: Path, *, map_bytes: bytes, restoration_verified: bool,
            expected_frames: int = 900) -> Path:
    """Project sealed actor/camera observations, encode, and seal after restore.

    ``expected_frames`` is 900 in production; a shorter value only supports
    the fake Native unit test and does not qualify a delivery attempt.
    """
    if restoration_verified is not True:
        raise ValueError("Native world restoration must be verified before sealing")
    root = Path(root)
    trace = json.loads((root / "native-trace.json").read_text())
    rows = trace.get("frames")
    if trace.get("source_kind") != "native_original" or not isinstance(rows, list) or len(rows) != expected_frames:
        raise ValueError("incomplete original Native frame source")
    if expected_frames <= 0 or type(map_bytes) is not bytes or not map_bytes:
        raise ValueError("original map bytes or frame count missing")
    map_sha = hashlib.sha256(map_bytes).hexdigest()
    if trace.get("fixed_context", {}).get("map_sha256") != map_sha:
        raise ValueError("original map bytes differ from sealed site")
    if (root / "capture-seal.json").exists() or (root / "road.xodr").exists():
        raise ValueError("original capture has already been published")
    road = root / "road.xodr"
    road.write_bytes(map_bytes)
    frame_map, ordinary_trace, evidence, native_frames = [], [], [], []
    from traffic_spec_adapter.adapter import write_adapter_graph
    import networkx as nx
    for index, row in enumerate(rows):
        frame = row["frame_id"]
        time_s = row["sim_time_s"]
        if type(frame) is not int or (index and frame != rows[index - 1]["frame_id"] + 1):
            raise ValueError("original Native frame identities changed")
        if index and abs(time_s - rows[index - 1]["sim_time_s"] - 0.05) > 1e-4:
            raise ValueError("original Native clock changed")
        position = row.get("parked_position_m")
        body = row.get("parked_body_vertices_m")
        if not isinstance(position, list) or len(position) != 3 or not isinstance(body, list) or len(body) < 4:
            raise ValueError("original parked actor source missing")
        passing_body = row.get("passing_body_vertices_m")
        passing_velocity = row.get("passing_velocity_mps")
        passing_position = row.get("passing_position_m")
        if (not isinstance(passing_body, list) or len(passing_body) < 4 or
                not isinstance(passing_velocity, list) or len(passing_velocity) != 3 or
                not isinstance(passing_position, list) or len(passing_position) != 3 or
                not str(row.get("parked_blueprint", "")).startswith("vehicle.") or
                not str(row.get("passing_blueprint", "")).startswith("vehicle.") or
                row.get("parked_blueprint_attributes", {}).get("base_type") not in
                ("car", "bus", "truck") or
                row.get("passing_blueprint_attributes", {}).get("base_type") not in
                ("car", "bus", "truck") or
                not str(row.get("driver_blueprint", "")).startswith("walker.") or
                not isinstance(row.get("driver_body_vertices_m"), list) or
                len(row["driver_body_vertices_m"]) < 4 or
                not isinstance(row.get("driver_velocity_mps"), list) or
                len(row["driver_velocity_mps"]) != 3):
            raise ValueError("original passing actor or blueprint source missing")
        parked_actor = {"actor_id": int(trace["fixed_context"]["parked_vehicle_id"]),
                        "blueprint": row["parked_blueprint"], "body_vertices_m": body,
                        "blueprint_attributes": row["parked_blueprint_attributes"],
                        "heading_deg": row["parked_heading_deg"],
                        "velocity_mps": row["parked_velocity_mps"],
                        "speed_mps": row["parked_speed_mps"]}
        passing_actor = {"actor_id": int(trace["fixed_context"]["passing_vehicle_id"]),
                         "blueprint": row["passing_blueprint"],
                         "blueprint_attributes": row["passing_blueprint_attributes"],
                         "body_vertices_m": passing_body,
                         "heading_deg": row["passing_heading_deg"],
                         "velocity_mps": passing_velocity,
                         "speed_mps": row["passing_speed_mps"]}
        driver_actor = {"actor_id": int(trace["fixed_context"]["driver_id"]),
                        "blueprint": row["driver_blueprint"],
                        "blueprint_attributes": row["driver_blueprint_attributes"],
                        "body_vertices_m": row["driver_body_vertices_m"],
                        "heading_deg": row["driver_heading_deg"],
                        "velocity_mps": row["driver_velocity_mps"],
                        "speed_mps": row["driver_speed_mps"]}
        source_packet = {"frame": frame, "time_s": time_s,
                         "participants": [parked_actor, passing_actor, driver_actor],
                         "door_interaction_observation": {
                             "observed_act": row["observed_act"],
                             "act_side": row.get("act_side"),
                             "passing_body_xy": row["passing_body_xy"],
                             "passing_speed_mps": row["passing_speed_mps"]},
                         "map_context": {"source_map_sha256": map_sha}}
        graph = nx.DiGraph()
        graph.graph.update(frame=frame, time_s=time_s, observed_evidence=source_packet)
        graph_name = f"graphs/base/{frame:08d}.adapter.json"
        graph_path = root / "capture/native" / graph_name
        graph_path.parent.mkdir(parents=True, exist_ok=True)
        write_adapter_graph(graph, graph_path)
        native_frames.append({"frame": frame, "simulation_time": time_s,
                              "adapter_graph": graph_name})
        frame_map.append({"video_frame": index, "carla_frame": frame,
                          "native_frame": frame, "time_s": time_s})
        speed = row["parked_speed_mps"]
        ordinary_trace.append({"frame": frame, "time_s": time_s,
                               "position": dict(zip(("x", "y", "z"), position)),
                               "position_m": position, "velocity_mps": row["parked_velocity_mps"],
                               "heading_deg": row["parked_heading_deg"],
                               "speed_mps": speed, "speed_mph": speed / 0.44704,
                               "control": {}})
        evidence.append({"actor_id": int(trace["fixed_context"]["parked_vehicle_id"]),
                         "original_frame": frame, "replay_frame": frame,
                         "recording_time_s": time_s,
                         "replay_simulation_time_s": time_s,
                         "ego": {"body_vertices_m": body, "position_m": position,
                                 "heading_deg": row["parked_heading_deg"],
                                 "speed_mps": speed,
                                 "speed_provenance": "original_native_actor_get_velocity"},
                         "original_observations": source_packet,
                         "world": {"weather": {}}})
    write_jsonl(root / "video_frames.jsonl", frame_map)
    write_jsonl(root / "trace.jsonl", ordinary_trace)
    write_jsonl(root / "capture/evidence.jsonl", evidence)
    write_jsonl(root / "capture/native/frames.jsonl", native_frames)
    (root / "capture/recorder_info.txt").write_text(
        f'Create {trace["fixed_context"]["parked_vehicle_id"]}: {rows[0]["parked_blueprint"]} at surveyed loading site\n')
    write_json(root / "capture/manifest.json", {
        "acquisition": "original_live_run", "diagnostic_fixture": False,
        "extraction_confirmed": True, "frames": len(rows),
        "sources": {"road.xodr": sha(road), "trace.jsonl": sha(root / "trace.jsonl")},
        "scope": "original Native door, actor and four RGB callback sources"})
    for view, target in VIEWS.items():
        encode_view(root, rows, view, target)
    write_json(root / "acquisition-provenance.json", {
        "provenance_kind": "native", "diagnostic_fixture": False,
        "physical_acceptance_claimed": False})
    from worker_exchange.native_output import seal_capture
    seal_capture(root, frames=len(rows), restoration={"restored": True}, errors=[],
                 encoder_exit_codes={target: 0 for target in VIEWS.values()},
                 context={"map_sha256": map_sha, "survey_sha256": trace["fixed_context"]["survey_sha256"],
                          "physical_acceptance_claimed": False})
    return root / "capture-seal.json"
