"""Publish a sealed original school-bus capture in the pinned Native format."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from native_capture import FRAMES, RATE, VIEWS
from school_scene_construction import ASSIGNMENT, load_case


def require(ok, message):
    if not ok:
        raise ValueError(message)


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
            stream.write(json.dumps(row, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False) + "\n")


def publish(root, *, map_bytes, restored):
    """Bridge original readbacks; refuse any rewritten source or partial capture."""
    require(restored is True and type(map_bytes) is bytes and bool(map_bytes),
            "original Native restoration and loaded OpenDRIVE bytes required")
    root = Path(root)
    receipt_path = root / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    sources = {"context_sha256": root / "context.json",
               "trace_sha256": root / "original-trace.jsonl",
               "camera_manifest_sha256": root / "cameras.json"}
    for key, path in sources.items():
        require(receipt.get(key) == sha(path), "sealed original Native source changed: " + path.name)
    context = json.loads(sources["context_sha256"].read_text())
    rows = [json.loads(line) for line in sources["trace_sha256"].read_text().splitlines()]
    cameras = json.loads(sources["camera_manifest_sha256"].read_text())
    case_id = receipt.get("case_id")
    require(isinstance(case_id, str) and case_id.startswith(ASSIGNMENT + "__"),
            "exact school-bus case identity required")
    case = load_case(case_id)
    require(context.get("case_id") == case_id and cameras.get("case_id") == case_id and
            receipt.get("assignment_id") == ASSIGNMENT and
            receipt.get("source_kind") == "original_native_capture" and
            receipt.get("diagnostic_fixture") is False,
            "original school-bus capture identity or provenance differs")
    require(len(rows) == FRAMES and receipt.get("frame_count") == FRAMES and
            cameras.get("frame_count") == FRAMES and receipt.get("fps") == RATE and
            cameras.get("fps") == RATE,
            "original Native capture duration incomplete")
    streams = cameras.get("streams")
    require(isinstance(streams, dict) and set(streams) == set(VIEWS),
            "four original RGB camera streams required")
    for view in VIEWS:
        item = streams[view]
        require(item.get("path") == view + ".mkv" and item.get("sha256") ==
                sha(root / item["path"]) and item.get("frame_count") == FRAMES and
                item.get("fps") == RATE,
                "original synchronized camera stream differs: " + view)
    require(context.get("site_sha256") == receipt.get("site_sha256") and
            context.get("map_sha256") == hashlib.sha256(map_bytes).hexdigest(),
            "original reviewed site or loaded map differs")
    road = root / "road.xodr"
    require(not road.exists(), "original OpenDRIVE output already exists")
    road.write_bytes(map_bytes)
    from traffic_spec_adapter.adapter import write_adapter_graph
    from worker_exchange.native_output import seal_capture
    import networkx as nx

    trace, mapping, evidence, native = [], [], [], []
    previous = None
    actor_id = rows[0].get("actor_id")
    for index, row in enumerate(rows):
        frame, time_s = row.get("native_frame"), row.get("time_s")
        require(type(frame) is int and (previous is None or frame == previous + 1) and
                row.get("frame") == index and type(time_s) in (int, float) and
                math.isfinite(time_s) and abs(time_s - index / RATE) <= .002 and
                row.get("actor_id") == actor_id and row.get("vehicle_id") == context["vehicle_id"] and
                row.get("map_sha256") == context["map_sha256"],
                "original school-bus frame, time or actor identity discontinuity")
        previous = frame
        speed = row.get("bus_speed_mps")
        point, direction, body = (row.get("position_m"), row.get("heading_xy"),
                                  row.get("body_vertices_m"))
        require(type(speed) in (int, float) and math.isfinite(speed) and speed >= 0 and
                isinstance(point, list) and len(point) == 3 and
                isinstance(direction, list) and len(direction) == 2 and
                isinstance(body, list) and len(body) >= 4 and
                all(type(v) in (int, float) and math.isfinite(v) for v in point + direction),
                "original bus motion/body readback incomplete")
        magnitude = math.hypot(*direction)
        require(abs(magnitude - 1) <= .01, "original bus heading vector not normalized")
        heading = math.degrees(math.atan2(direction[1], direction[0]))
        velocity = [speed * direction[0], speed * direction[1], 0.0]
        participants = [{"actor_id": actor_id, "blueprint": row["vehicle_blueprint"],
                         "blueprint_attributes": {"base_type": "bus" if
                            case["vehicle_request"] == "motor_bus" else "car"},
                         "position_m": point, "body_vertices_m": body,
                         "heading_deg": heading, "velocity_mps": velocity,
                         "speed_mps": speed}]
        child_ids = row.get("children_actor_ids")
        children = row.get("children_actor_readback")
        require(isinstance(child_ids, list) and isinstance(children, list) and
                {str(child.get("actor_id")) for child in children} == set(child_ids),
                "original child actor inventory/body join failed")
        for child in children:
            participants.append({"actor_id": child["actor_id"],
                                 "blueprint": child["blueprint"],
                                 "blueprint_attributes": {"base_type": "pedestrian"},
                                 "position_m": child["position_m"],
                                 "body_vertices_m": child["body_vertices_m"],
                                 "heading_deg": child.get("heading_deg", 0.0),
                                 "velocity_mps": child.get("velocity_mps", [0, 0, 0]),
                                 "speed_mps": child.get("speed_mps", 0.0)})
        packet = {"frame": frame, "time_s": time_s, "participants": participants,
                  "world_settings": {"no_rendering_mode": False},
                  "rgb_sensors": [{"view": view, "source": "original_native_callback_rgb"}
                                  for view in VIEWS],
                  "school_bus_speed_observation": {"case_id": case_id,
                      "site_sha256": receipt["site_sha256"],
                      "inside_designated_zone": row["inside_designated_zone"],
                      "bus_speed_mps": speed,
                      "school_in_session_today": row["school_in_session_today"],
                      "beacon_yellow_lights_lit": row["beacon_yellow_lights_lit"],
                      "sign_limit_active": row["sign_limit_active"],
                      "children_actor_ids": child_ids}}
        graph = nx.DiGraph()
        graph.graph.update(frame=frame, time_s=time_s, observed_evidence=packet)
        graph_name = f"graphs/base/{frame:08d}.adapter.json"
        graph_path = root / "capture/native" / graph_name
        graph_path.parent.mkdir(parents=True, exist_ok=True)
        write_adapter_graph(graph, graph_path)
        native.append({"frame": frame, "simulation_time": time_s,
                       "adapter_graph": graph_name})
        mapping.append({"video_frame": index, "carla_frame": frame,
                        "native_frame": frame, "time_s": time_s})
        trace.append({"frame": frame, "time_s": time_s,
                      "position": dict(zip(("x", "y", "z"), point)),
                      "position_m": point, "velocity_mps": velocity,
                      "heading_deg": heading, "speed_mps": speed, "control": {}})
        evidence.append({"actor_id": actor_id, "original_frame": frame,
                         "replay_frame": frame, "recording_time_s": time_s,
                         "replay_simulation_time_s": time_s,
                         "ego": {"body_vertices_m": body, "position_m": point,
                                 "heading_deg": heading, "speed_mps": speed,
                                 "speed_provenance": "original_native_actor_readback"},
                         "original_observations": packet, "world": {"weather": {}}})
    write_jsonl(root / "trace.jsonl", trace)
    write_jsonl(root / "video_frames.jsonl", mapping)
    write_json(root / "comparison-packet.json", {
        "case_id": case_id[len(ASSIGNMENT) + 2:],
        "original_recording_id": sha(receipt_path), "scene": context, "frames": rows})
    write_jsonl(root / "capture/evidence.jsonl", evidence)
    write_jsonl(root / "capture/native/frames.jsonl", native)
    (root / "capture/recorder_info.txt").write_text("Original Native school-bus capture\n")
    write_json(root / "capture/manifest.json", {
        "acquisition": "original_live_run", "diagnostic_fixture": False,
        "extraction_confirmed": True, "frames": FRAMES,
        "observation_contract_version": 2,
        "sources": {"road.xodr": sha(road), "trace.jsonl": sha(root / "trace.jsonl")},
        "scope": "original school bus, zone, children, device and four RGB callbacks"})
    write_json(root / "acquisition-provenance.json", {
        "provenance_kind": "native", "diagnostic_fixture": False,
        "physical_acceptance_claimed": False})
    return seal_capture(root, frames=FRAMES, restoration={"restored": True}, errors=[],
                        encoder_exit_codes={view: 0 for view in VIEWS},
                        context={"map_sha256": sha(road),
                                 "site_sha256": receipt["site_sha256"],
                                 "physical_acceptance_claimed": False})
