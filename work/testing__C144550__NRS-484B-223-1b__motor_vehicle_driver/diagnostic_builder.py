"""Generate textual synthetic source fixtures for software compatibility only."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from worker_exchange.fixture_generator import _graph
from traffic_spec_adapter.adapter import write_adapter_graph

from native_construction import ASSIGNMENT

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
         "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"


def lines(rows):
    return "".join(encoded(row) for row in rows)


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def build(variant: str):
    if variant not in ("both_observed", "signal_missing", "check_missing"):
        raise ValueError("unknown controlled variant")
    case = ASSIGNMENT + "__" + variant
    source = json.loads((REPO / "runtime/fixtures/example.json").read_text())
    files = dict(source["files"])
    # The original generic graph is converter scaffolding only. Every measured
    # lane-change value below comes from independently joined synthetic packets.
    examples = [json.loads(line) for line in files["trace.jsonl"].splitlines()]
    example_trace = examples[0]
    initial_frame = example_trace["frame"]
    clock = [{"frame": initial_frame + i,
              "t_s": examples[i]["time_s"] if i < len(examples) else
              round(examples[-1]["time_s"] + (i - len(examples) + 1) * .05, 9)}
             for i in range(900)]
    trace = []
    mapping = []
    for i, row in enumerate(clock):
        sample = examples[i] if i < len(examples) else example_trace
        trace_row = {key: sample[key] for key in (
            "position", "position_m", "heading_deg", "speed_mps",
            "speed_mph", "velocity_mps", "control")}
        trace_row["frame"] = row["frame"]
        trace_row["time_s"] = row["t_s"]
        trace.append(trace_row)
        mapping.append({"video_frame": i, "carla_frame": row["frame"],
                        "native_frame": row["frame"], "time_s": row["t_s"]})
    files["trace.jsonl"] = lines(trace)
    files["video_frames.jsonl"] = lines(mapping)
    evidence_examples = [json.loads(line) for line in files["capture/evidence.jsonl"].splitlines()]
    frame_examples = [json.loads(line) for line in files["capture/native/frames.jsonl"].splitlines()]
    evidence = []
    native_frames = []
    for i, row in enumerate(clock):
        observed = evidence_examples[i] if i < len(evidence_examples) else evidence_examples[0]
        item = {key: observed[key] for key in ("actor_id", "ego", "world")}
        item.update({"original_frame": row["frame"], "replay_frame": row["frame"],
                     "recording_time_s": row["t_s"],
                     "replay_simulation_time_s": row["t_s"] + 13.517531131161377})
        item["original_observations"] = observation_packet(row)
        evidence.append(item)
        frame = frame_examples[i] if i < len(frame_examples) else frame_examples[0]
        native_frames.append({"frame": row["frame"],
            "simulation_time": item["replay_simulation_time_s"],
            "abstract": None, "base": None,
            "nodes": 7, "edges": 5,
            "adapter_graph": "graphs/base/%08d.adapter.json" % row["frame"]})
    files["capture/evidence.jsonl"] = lines(evidence)
    files["capture/native/frames.jsonl"] = lines(native_frames)
    capture_manifest = json.loads(files["capture/manifest.json"])
    capture_manifest["case_id"] = case
    capture_manifest["frames"] = 900
    capture_manifest["required_observations"] = []
    capture_manifest["source_run"] = "diagnostic:900-frame-synthetic-converter"
    capture_manifest["sources"]["trace.jsonl"] = sha(files["trace.jsonl"])
    files["capture/manifest.json"] = encoded(capture_manifest)
    packets = {
        "frame_map": {"samples": clock},
        "ego_pose": {"source_lane_id": "source-lane", "lane_geometry_source": "synthetic-marked-lane",
            "samples": [{**row, "x_m": round(i * .05, 9),
                         "y_m": 3.5 if i == 899 else 0.,
                         "source_lane_offset_m": .06 if i >= 4 else 0.}
                        for i, row in enumerate(clock)]},
        "native_signal": {"readback_source": "synthetic original API readback",
            "samples": [{**row, "left_signal": variant != "signal_missing" and i >= 1,
                         "right_signal": False} for i, row in enumerate(clock)]},
        "driver_check": {"readback_source": "synthetic independent driver input",
            "observation_method": "separate diagnostic input event",
            "samples": [{**row, "driver_check_observed":
                         variant != "check_missing" and i == 2} for i, row in enumerate(clock)]}}
    inventory = {"case_id": case, "source_kind": "original_native",
                 "original_trace_id": "diagnostic-synthetic-input", "sources": {}}
    for name, packet in packets.items():
        packet.update({"case_id": case, "source_kind": "original_native"})
        value = encoded(packet)
        files[name + ".json"] = value
        inventory["sources"][name] = {"path": name + ".json", "sha256": sha(value)}
    files["readback-inventory.json"] = encoded(inventory)
    traffic = [{**row, "target_x_m": 20., "target_y_m": 3.5} for row in clock]
    driver = [{**row, "source_kind": "original_driver_input",
               "source_id": "diagnostic-independent-driver", "observed":
               variant != "check_missing" and i == 2} for i, row in enumerate(clock)]
    files["target-traffic-history.jsonl"] = lines(traffic)
    files["original-driver-input.jsonl"] = lines(driver)
    cameras = [{"frame": i, "native_frame": row["frame"],
                "native_elapsed_s": row["t_s"],
                "views": {name: {"path": name + ".mkv"} for name in VIEWS}}
               for i, row in enumerate(clock)]
    files["original-camera-frames/camera-manifest.json"] = encoded(cameras)
    site = {"reviewed_provenance": {"reviewer": "synthetic diagnostic only",
             "lane_marking_source": "synthetic fixture; no physical review"},
            "lanes": {"source": {"lane_id": "source-lane"},
                "destination": {"lane_id": "destination-lane",
                    "centerline_world_xyz_m": [[i * 5., 3.5, 0.] for i in range(10)]}},
            "ego_blueprint": "vehicle.fixture", "target_vehicle_blueprint": "vehicle.fixture-target",
            "target_spawn_xyz_yaw": [20., 3.5, 0., 0.],
            "camera_poses_xyz_pitch_yaw": {name: [0, 0, 5, 0, 0] for name in VIEWS}}
    files["reviewed-site.json"] = encoded(site)
    files["acquisition-provenance.json"] = encoded({"provenance_kind": "synthetic_fixture",
        "diagnostic_fixture": True})
    files["lane-change-capture-receipt.json"] = encoded({
        "native_frame_count": 900, "readback_inventory": inventory,
        "target_traffic": {"sha256": sha(files["target-traffic-history.jsonl"])},
        "original_driver_input": {"sha256": sha(files["original-driver-input.jsonl"]),
                                  "source_id": "diagnostic-independent-driver"},
        "camera_manifest": {"sha256": sha(files["original-camera-frames/camera-manifest.json"])}})
    source["files"] = files
    source["graphs"] = []
    source["videos"] = [{"path": name + ".mkv", "frames": 900,
                         "width": SIZES[name][0], "height": SIZES[name][1],
                         "fps": 20, "color": "black"} for name in VIEWS]
    return source


def write_graphs(clock):
    """Provide a frame-indexed adapter graph for every synthetic source tick."""
    sample = json.loads((REPO / "runtime/fixtures/example.json").read_text())["graphs"][0]
    chosen = [node for node in sample["nodes"] if node["id"] == "ego" or
              node["attributes"].get("waypoint_s", 999) in
              (98.0, 99.0, 100.0, 101.0, 102.0, 103.0)]
    ids = {node["id"] for node in chosen}
    attributes = {key: val for key, val in sample["attributes"].items()
                  if key != "observed_evidence"}
    for key in ("bbox", "node_colors", "node_size"):
        attributes[key] = {node: val for node, val in attributes[key].items()
                           if node in ids}
    source_edges = [edge for edge in sample["edges"]
                    if edge["source"] in ids and edge["target"] in ids]
    sources = []
    for row in clock:
        frame = row["frame"]
        path = "capture/native/graphs/base/%08d.adapter.json" % frame
        target = HERE / "diagnostic-common" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        attrs = dict(attributes, frame=frame,
                     simulation_time_s=row["t_s"] + 13.517531131161377,
                     observed_evidence=observation_packet(row))
        graph = {"path": path, "attributes": attrs, "nodes": chosen,
                 "edges": source_edges}
        write_adapter_graph(_graph(graph), target)
        sources.append({"path": path, "source": str(target.relative_to(REPO)),
                        "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    return sources


def observation_packet(row):
    return {"frame": row["frame"], "time_s": row["t_s"],
            "world_settings": {"no_rendering_mode": False},
            "rgb_sensors": [{"actor_id": 209, "blueprint": "sensor.camera.rgb"}],
            "participants": [], "devices": [], "relations": [],
            "map_context": {"declared_public_way_road_ids": [1]}}


def write():
    sample = json.loads((REPO / "runtime/fixtures/example.json").read_text())
    example_trace = [json.loads(line) for line in sample["files"]["trace.jsonl"].splitlines()]
    clock = [{"frame": example_trace[0]["frame"] + i,
              "t_s": example_trace[i]["time_s"] if i < len(example_trace) else
              round(example_trace[-1]["time_s"] +
                    (i - len(example_trace) + 1) * .05, 9)} for i in range(900)]
    graph_sources = write_graphs(clock)
    for variant in ("both_observed", "signal_missing", "check_missing"):
        folder = HERE / "cases" / variant
        value = build(variant)
        original = sample
        extra = sorted(set(value["files"]) - set(original["files"]))
        sources = list(graph_sources)
        for name in ("capture/evidence.jsonl", "capture/native/frames.jsonl",
                     "capture/manifest.json"):
            target = folder / "fixture-sources" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(value["files"].pop(name))
            sources.append({"path": name, "source": str(target.relative_to(REPO)),
                            "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
        for name in extra:
            target = folder / "fixture-sources" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(value["files"].pop(name))
            if target.stat().st_size > 2 * 1024 * 1024:
                raise ValueError("diagnostic source component exceeds returned file cap")
            sources.append({"path": name,
                "source": str(target.relative_to(REPO)),
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
        path = folder / "diagnostic.json"
        path.write_text(json.dumps(value, separators=(",", ":")) + "\n")
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("diagnostic source exceeds returned file cap")
        recipe = {"format": "worker-fixture-recipe", "sources": sources,
                  "generator": {"source": str(path.relative_to(REPO)),
                                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}}
        (folder / "diagnostic-recipe.json").write_text(
            json.dumps(recipe, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    write()
