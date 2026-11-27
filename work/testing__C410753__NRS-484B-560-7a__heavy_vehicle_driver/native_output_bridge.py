"""Publish restored railway Native packets as sealed original Core capture."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import subprocess

from native_capture import FRAME_COUNT, VIEWS
import railway_7a as law

ASSIGNMENT = "testing__C410753__NRS-484B-560-7a__heavy_vehicle_driver"


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
        raise ValueError("sealed 900-frame railway source inventory incomplete")
    for name, filename in (("site", "site.json"), ("history", "history.json"),
                           ("frame_map", "frame-map.json")):
        if refs[name].get("path") != filename or refs[name].get("sha256") != _sha(root / filename):
            raise ValueError("sealed railway Native packet source differs")
    site = json.loads((root / "site.json").read_text())
    rows = json.loads((root / "history.json").read_text())
    frame_map = json.loads((root / "frame-map.json").read_text())
    if site.get("map_sha256") != hashlib.sha256(map_bytes).hexdigest():
        raise ValueError("loaded OpenDRIVE differs from reviewed railway map")
    case_id = inventory.get("case_id")
    if not isinstance(case_id, str) or not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("exact railway case mismatch")
    case_name = case_id.removeprefix(ASSIGNMENT + "__")
    law.validate_site(site, case_name)
    measured = law.measure_frames(site, rows)
    if len(rows) != FRAME_COUNT or len(frame_map) != FRAME_COUNT:
        raise ValueError("original railway history/frame map incomplete")
    road = root / "road.xodr"
    if road.exists():
        raise ValueError("original OpenDRIVE output already exists")
    road.write_bytes(map_bytes)
    from traffic_spec_adapter.adapter import write_adapter_graph
    from worker_exchange.native_output import seal_capture
    import networkx as nx
    trace, mapping, evidence, native = [], [], [], []
    for index, row in enumerate(rows):
        number = row.get("source_frame")
        if type(number) is not int or (index and number != rows[index - 1]["source_frame"] + 1):
            raise ValueError("original Native frame identity gap")
        if frame_map[index] != {"frame_index": index, "native_frame": number,
                                "time_s": row["time_s"]}:
            raise ValueError("original railway frame-map join differs")
        position = row["vehicle_position_m"]
        heading = math.degrees(math.atan2(row["heading_xy"][1], row["heading_xy"][0]))
        velocity = [row["speed_mps"] * row["heading_xy"][0],
                    row["speed_mps"] * row["heading_xy"][1], 0.0]
        participants = []
        for offset, unit in enumerate(row["vehicle_units"]):
            blueprint = unit.get("blueprint_id")
            if not isinstance(blueprint, str) or not blueprint.startswith("vehicle."):
                raise ValueError("actual heavy/coupled vehicle blueprint missing")
            try:
                actor_id = int(unit["actor_id"])
            except (ValueError, TypeError):
                raise ValueError("actual heavy/coupled actor ID invalid") from None
            unit_heading = math.degrees(math.atan2(unit["heading_xy"][1], unit["heading_xy"][0]))
            participants.append({"actor_id": actor_id, "blueprint": blueprint,
                                 "blueprint_attributes": {"base_type": "truck" if offset == 0 else "trailer"},
                                 "position_m": unit["position_m"],
                                 "body_vertices_m": unit["body_vertices_m"],
                                 "heading_deg": unit_heading,
                                 "velocity_mps": unit["velocity_mps"],
                                 "speed_mps": math.dist(unit["velocity_mps"], [0.0, 0.0, 0.0])})
        packet = {"frame": number, "time_s": row["time_s"],
                  "participants": participants,
                  "world_settings": {"no_rendering_mode": False},
                  "rgb_sensors": [{"view": name, "source": "original_native_callback_rgb"}
                                  for name in VIEWS],
                  "railway_7a_observation": {
                      "site_sha256": inventory["reviewed_site_sha256"],
                      "rail_geometry": site["track"]["rails"],
                      "crossing_axis_unit": site["crossing_axis_unit"],
                      "trailing_end_past_nearest_rail_ft":
                          measured["samples"][index]["trailing_end_past_nearest_rail_ft"],
                      "downstream_body_gap_m": row["downstream_body_gap_m"],
                      "undercarriage_contact": row["undercarriage_contact"],
                      "contact_source_ref": row["contact_source_ref"],
                      "control_source_ref": row["control_source_ref"],
                      "traffic_conflict_source_ref": row["traffic_conflict_source_ref"],
                      "traffic_conflict": row["traffic_conflict"],
                      "brake_applied": row["brake_applied"],
                      "legal_judgment": "unresolved"}}
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
                      "position": {"x": position[0], "y": position[1], "z": position[2]},
                      "position_m": position, "velocity_mps": velocity,
                      "heading_deg": heading, "speed_mps": row["speed_mps"],
                      "control": {"brake_applied": row["brake_applied"]}})
        evidence.append({"actor_id": participants[0]["actor_id"],
                         "original_frame": number, "replay_frame": number,
                         "recording_time_s": row["time_s"],
                         "replay_simulation_time_s": row["time_s"],
                         "ego": {"body_vertices_m": participants[0]["body_vertices_m"],
                                 "position_m": position, "heading_deg": heading,
                                 "speed_mps": row["speed_mps"],
                                 "speed_provenance": "original_native_actor_readback"},
                         "original_observations": packet, "world": {"weather": {}}})
    _jsonl(root / "trace.jsonl", trace)
    _jsonl(root / "video_frames.jsonl", mapping)
    _jsonl(root / "capture/evidence.jsonl", evidence)
    _jsonl(root / "capture/native/frames.jsonl", native)
    (root / "capture/recorder_info.txt").write_text("Original Native railway crossing capture\n")
    _write(root / "capture/manifest.json", {
        "acquisition": "original_live_run", "diagnostic_fixture": False,
        "extraction_confirmed": True, "frames": FRAME_COUNT,
        "observation_contract_version": 2,
        "sources": {"road.xodr": _sha(road), "trace.jsonl": _sha(root / "trace.jsonl")},
        "scope": "original heavy and coupled units, railway geometry, obstruction/contact and four RGB views"})
    for view in VIEWS:
        _encode(root, rows, view)
    _write(root / "acquisition-provenance.json", {
        "provenance_kind": "native", "diagnostic_fixture": False,
        "physical_acceptance_claimed": False})
    return seal_capture(root, frames=FRAME_COUNT, restoration={"restored": True},
                        errors=[], encoder_exit_codes={view: 0 for view in VIEWS},
                        context={"map_sha256": _sha(road),
                                 "site_sha256": inventory["reviewed_site_sha256"],
                                 "maximum_trailing_end_ft": measured["maximum_trailing_end_ft"],
                                 "causal_attribution": "requires independent source review",
                                 "physical_acceptance_claimed": False})
