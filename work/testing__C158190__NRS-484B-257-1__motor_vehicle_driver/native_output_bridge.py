"""Publish restored yield-site source packets into the pinned Core format."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from native_capture import FRAMES, VIEWS
from yield_view_measurement import ASSIGNMENT


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, separators=(",", ":"), allow_nan=False)
        stream.write("\n")


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False) + "\n")


def publish(root: Path, *, map_bytes: bytes, restored: bool) -> dict:
    require(restored is True and type(map_bytes) is bytes and bool(map_bytes),
            "original Native restoration and OpenDRIVE bytes required")
    root = Path(root)
    receipt = json.loads((root / "receipt.json").read_text())
    context_path, original_path, camera_path = (root / name for name in
                                                ("context.json", "original-trace.jsonl", "cameras.json"))
    for key, path in (("context_sha256", context_path), ("trace_sha256", original_path),
                      ("camera_manifest_sha256", camera_path)):
        require(receipt.get(key) == sha(path), "sealed Native packet changed: " + path.name)
    context = json.loads(context_path.read_text())
    rows = [json.loads(line) for line in original_path.read_text().splitlines()]
    cameras = json.loads(camera_path.read_text())
    case_id = receipt.get("case_id")
    require(case_id.startswith(ASSIGNMENT + "__") and context.get("case_id") == case_id and
            cameras.get("case_id") == case_id and receipt.get("source_kind") == "original_native_capture",
            "exact original Native case identity mismatch")
    require(len(rows) == FRAMES and receipt.get("frame_count") == FRAMES and
            cameras.get("frame_count") == FRAMES and receipt.get("fps") == 20 and
            cameras.get("fps") == 20,
            "original Native capture duration incomplete")
    streams = cameras.get("streams", {})
    require(set(streams) == set(VIEWS), "four original RGB camera streams missing")
    for view in VIEWS:
        item = streams[view]
        require(item.get("path") == view + ".mkv" and
                item.get("sha256") == sha(root / item["path"]),
                "original camera stream changed: " + view)
    require(context.get("site_sha256") == receipt.get("site_sha256") and
            context.get("map_source_sha256") == hashlib.sha256(map_bytes).hexdigest(),
            "original reviewed site or loaded map changed")
    road = root / "road.xodr"
    require(not road.exists(), "original OpenDRIVE output already exists")
    road.write_bytes(map_bytes)
    from traffic_spec_adapter.adapter import write_adapter_graph
    from worker_exchange.native_output import seal_capture
    import networkx as nx
    trace, mapping, evidence, native = [], [], [], []
    last_frame = None
    actor_id = rows[0]["actor_id"]
    for index, row in enumerate(rows):
        number = row.get("native_frame")
        require(type(number) is int and (last_frame is None or number == last_frame + 1) and
                row.get("frame") == index and abs(row.get("time_s", -1000) - index / 20) <= .002 and
                row.get("actor_id") == actor_id,
                "original Native frame, time or actor identity discontinuity")
        last_frame = number
        x, y, z = row["position_m"]
        hx, hy = row["heading_xy"]
        heading = math.degrees(math.atan2(hy, hx))
        speed = row["ego_speed_mps"]
        velocity = [speed * hx, speed * hy, 0.0]
        participant = {"actor_id": actor_id, "blueprint": row["vehicle_blueprint"],
                       "blueprint_attributes": {"base_type": "car"},
                       "position_m": [x, y, z], "body_vertices_m": row["body_vertices_m"],
                       "heading_deg": heading, "velocity_mps": velocity, "speed_mps": speed}
        packet = {"frame": number, "time_s": row["time_s"],
                  "participants": [participant],
                  "world_settings": {"no_rendering_mode": False},
                  "rgb_sensors": [{"view": view, "source": "original_native_callback_rgb"}
                                  for view in VIEWS],
                  "yield_observation": {"case_id": case_id,
                      "site_sha256": receipt["site_sha256"],
                      "ego_within_intersection": row["ego_within_intersection"],
                      "through_vehicle_ids": row["through_vehicle_ids"],
                      "nearest_view_stations": context.get("approach_view_stations")}}
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
                      "position": {"x": x, "y": y, "z": z}, "position_m": [x, y, z],
                      "velocity_mps": velocity, "heading_deg": heading,
                      "speed_mps": speed, "control": {}})
        evidence.append({"actor_id": actor_id, "original_frame": number,
                         "replay_frame": number, "recording_time_s": row["time_s"],
                         "replay_simulation_time_s": row["time_s"],
                         "ego": {"body_vertices_m": row["body_vertices_m"],
                                 "position_m": [x, y, z], "heading_deg": heading,
                                 "speed_mps": speed,
                                 "speed_provenance": "original_native_actor_readback"},
                         "original_observations": packet, "world": {"weather": {}}})
    write_jsonl(root / "trace.jsonl", trace)
    write_jsonl(root / "video_frames.jsonl", mapping)
    write_json(root / "comparison-packet.json", {
        "case_id": case_id[len(ASSIGNMENT) + 2:],
        "original_recording_id": sha(root / "receipt.json"),
        "assignment_id": ASSIGNMENT,
        "original_trace_id": sha(root / "original-trace.jsonl"),
        "site": context,
        "frames": rows})
    write_jsonl(root / "capture/evidence.jsonl", evidence)
    write_jsonl(root / "capture/native/frames.jsonl", native)
    (root / "capture/recorder_info.txt").write_text("Original Native yield approach capture\n")
    write_json(root / "capture/manifest.json", {
        "acquisition": "original_live_run", "diagnostic_fixture": False,
        "extraction_confirmed": True, "frames": FRAMES,
        "observation_contract_version": 2,
        "sources": {"road.xodr": sha(road), "trace.jsonl": sha(root / "trace.jsonl")},
        "scope": "original yield sign, no-line/no-crosswalk nearest-view crossing and four RGB callbacks"})
    write_json(root / "acquisition-provenance.json", {
        "provenance_kind": "native", "diagnostic_fixture": False,
        "physical_acceptance_claimed": False})
    return seal_capture(root, frames=FRAMES, restoration={"restored": True}, errors=[],
                        encoder_exit_codes={view: 0 for view in VIEWS},
                        context={"map_sha256": sha(road),
                                 "site_sha256": receipt["site_sha256"],
                                 "physical_acceptance_claimed": False})
