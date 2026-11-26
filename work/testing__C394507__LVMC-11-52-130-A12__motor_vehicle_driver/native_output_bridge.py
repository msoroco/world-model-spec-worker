"""Export restored original crossing capture into sealed Core source artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile

import crosswalk_site as crossing
from native_capture import FPS, FRAMES, VIEWS


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, separators=(",", ":"), allow_nan=False)
        stream.write("\n")


def jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")


def encode(root, view, rows):
    target = root / (view + ".mkv")
    command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
               "-f", "image2pipe", "-framerate", str(FPS), "-vcodec", "png", "-i", "-",
               "-an", "-c:v", "ffv1", "-threads", "1", str(target)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        with ZipFile(root / (view + ".png.zip")) as archive:
            for row in rows:
                member = row["camera_frames"][view]
                data = archive.read(member["member"])
                if hashlib.sha256(data).hexdigest() != member["sha256"]:
                    raise ValueError("original camera source changed: " + view)
                process.stdin.write(data)
        process.stdin.close()
        error = process.stderr.read()
        if process.wait(timeout=300) != 0:
            raise ValueError("original camera encoding failed: " +
                             error.decode(errors="replace")[-400:])
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
    history = json.loads((root / "original-crosswalk-history.json").read_text())
    site = json.loads((root / "original-site.json").read_text())
    rows = history["samples"]
    if (history.get("diagnostic_fixture") is not False or
            history.get("source_kind") != "original_native" or
            history.get("frame_count") != FRAMES or len(rows) != FRAMES or
            history.get("site_sha256") != sha(root / "original-site.json") or
            site.get("map_sha256") != hashlib.sha256(map_bytes).hexdigest()):
        raise ValueError("original crosswalk sources are incomplete or changed")
    case_id = history.get("case_id", "")
    if not case_id.startswith(crossing.ASSIGNMENT_ID + "__"):
        raise ValueError("exact crossing case missing")
    for name, record in site["source_records"].items():
        if sha(root / record["path"]) != record["sha256"]:
            raise ValueError("reviewed source changed: " + name)
    (root / "road.xodr").write_bytes(map_bytes)
    from traffic_spec_adapter.adapter import write_adapter_graph
    from worker_exchange.native_output import seal_capture
    import networkx as nx
    trace, mapping, evidence, native = [], [], [], []
    previous = None
    for index, row in enumerate(rows):
        frame, time_s = row["frame"], row["time_s"]
        if (type(frame) is not int or (previous is not None and frame != previous + 1) or
                abs(time_s - index / FPS) > .005 or
                set(row.get("camera_frames", {})) != set(VIEWS)):
            raise ValueError("original source frame, clock or camera join changed")
        previous = frame
        position = row["position_m"]
        velocity = row["velocity_mps"]
        participant = {"actor_id": int(row["actor_id"]),
                       "blueprint": row["vehicle_blueprint"],
                       "blueprint_attributes": {"base_type": "car"},
                       "position_m": position, "body_vertices_m": row["body_vertices_m"],
                       "heading_deg": row["heading_deg"], "velocity_mps": velocity,
                       "speed_mps": row["ego_speed_mps"]}
        packet = {"frame": frame, "time_s": time_s, "participants": [participant],
                  "world_settings": {"no_rendering_mode": False},
                  "rgb_sensors": [{"view": view, "source": "original_native_callback_rgb"}
                                  for view in VIEWS],
                  "crosswalk_observation": {
                      "road_id": row["road_id"], "lane_id": row["lane_id"],
                      "crosswalk_marked": site["crosswalk_marked"],
                      "crossing_polygon_xy_m": site["crossing_polygon_xy_m"],
                      "ego_body_polygon_xy_m": row["ego_body_polygon_xy_m"],
                      "activity_readback": row["activity_readback"],
                      "exception_readback": row["exception_readback"],
                      "map_sha256": site["map_sha256"]}}
        graph = nx.DiGraph()
        graph.graph.update(frame=frame, time_s=time_s, observed_evidence=packet)
        graph_name = f"graphs/base/{frame:08d}.adapter.json"
        target = root / "capture/native" / graph_name
        target.parent.mkdir(parents=True, exist_ok=True)
        write_adapter_graph(graph, target)
        native.append({"frame": frame, "simulation_time": time_s,
                       "adapter_graph": graph_name})
        mapping.append({"video_frame": index, "carla_frame": frame,
                        "native_frame": frame, "time_s": time_s})
        trace.append({"frame": frame, "time_s": time_s,
                      "position": dict(zip(("x", "y", "z"), position)),
                      "position_m": position, "velocity_mps": velocity,
                      "heading_deg": row["heading_deg"],
                      "speed_mps": row["ego_speed_mps"], "control": {}})
        evidence.append({"actor_id": int(row["actor_id"]),
                         "original_frame": frame, "replay_frame": frame,
                         "recording_time_s": time_s, "replay_simulation_time_s": time_s,
                         "ego": {"body_vertices_m": row["body_vertices_m"],
                                 "position_m": position,
                                 "heading_deg": row["heading_deg"],
                                 "speed_mps": row["ego_speed_mps"],
                                 "speed_provenance": "original_native_actor_readback"},
                         "original_observations": packet, "world": {"weather": {}}})
    jsonl(root / "trace.jsonl", trace)
    jsonl(root / "body_history.jsonl", [
        {"frame": row["frame"], "time_s": row["time_s"],
         "body_vertices_m": row["body_vertices_m"]} for row in rows])
    jsonl(root / "video_frames.jsonl", mapping)
    jsonl(root / "capture/evidence.jsonl", evidence)
    jsonl(root / "capture/native/frames.jsonl", native)
    (root / "capture/recorder_info.txt").write_text("Original Native crosswalk capture\n")
    write(root / "capture/manifest.json", {
        "acquisition": "original_live_run", "diagnostic_fixture": False,
        "extraction_confirmed": True, "frames": FRAMES,
        "observation_contract_version": 2,
        "sources": {"road.xodr": sha(root / "road.xodr"),
                    "trace.jsonl": sha(root / "trace.jsonl")},
        "scope": "original crosswalk actor, full body, context and four RGB callbacks"})
    for view in VIEWS:
        encode(root, view, rows)
    write(root / "acquisition-provenance.json", {
        "provenance_kind": "native", "diagnostic_fixture": False,
        "physical_acceptance_claimed": False})
    return seal_capture(root, frames=FRAMES, restoration={"restored": True},
                        errors=[], encoder_exit_codes={view: 0 for view in VIEWS},
                        context={"map_sha256": sha(root / "road.xodr"),
                                 "site_sha256": sha(root / "original-site.json"),
                                 "physical_acceptance_claimed": False})
