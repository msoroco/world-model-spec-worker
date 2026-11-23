"""Author text-only converter diagnostics from the existing synthetic attempt."""
import copy
import hashlib
import json
import math
import sys
from pathlib import Path

root = Path.cwd()
folder = root / "work/testing__C202480__NRS-484B-560-3__motor_vehicle_driver"
sys.path.insert(0, str(folder / "tests"))
from test_saved_measurement import SavedMeasurementTests

template = json.loads((root / "runtime/fixtures/example.json").read_text())
sample = json.loads(template["files"]["capture/evidence.jsonl"].splitlines()[0])
graph = copy.deepcopy(template["graphs"][0])
graph["path"] = "capture/native/graphs/base/template.adapter.json"
sys.path.insert(0, str(root / "runtime"))
from scenario_pipeline.worker_exchange.fixture_generator import _graph
from traffic_spec_adapter.adapter import write_adapter_graph
graph_template_path = root / ".runtime-work/c202480-fixture-graph-template.adapter.json"
write_adapter_graph(_graph(template["graphs"][0]), graph_template_path)
graph_template = json.loads(graph_template_path.read_text())
selected = {}
for node in graph_template["nodes"]:
    a = node["attributes"]
    if a.get("sem_class") == "Driving":
        key = (a.get("waypoint_road_id"), a.get("waypoint_section_id"), a.get("waypoint_lane_id"))
        selected.setdefault(key, node)
ego_template = next(node for node in graph_template["nodes"] if node["attributes"].get("sem_class") == "ego")
small_graph = {**graph_template, "nodes": [*selected.values(), ego_template], "edges": []}
media = root / ".runtime-work/c202480-fixture-media"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for index in range(6):
    fixture = SavedMeasurementTests()
    fixture.case_index = index
    fixture.setUp()
    try:
        attempt = fixture.attempt
        suffix = fixture.case_id.rsplit("__", 1)[-1]
        source_root = folder / "diagnostic_sources" / suffix
        trace = [json.loads(line) for line in (attempt / "trace.jsonl").read_text().splitlines()]
        media_receipt = json.loads((attempt / "media-receipt.json").read_text())
        for name in media_receipt["video_sha256"]:
            media_receipt["video_sha256"][name] = digest(media / (name + ".mkv"))
        (attempt / "media-receipt.json").write_text(json.dumps(media_receipt))
        files = {p.relative_to(attempt).as_posix(): p.read_text()
                 for p in attempt.rglob("*") if p.is_file() and p.suffix != ".mkv"}
        for name in ("road.xodr",):
            files[name] = template["files"][name]
        packet = json.loads(files["site/packet.json"])
        files["capture/recorder_info.txt"] = (
            "Version: 1\nMap: OpenDriveMap\n Create " +
            str(trace[0]["ego"]["actor_id"]) + ": " +
            packet["vehicle_blueprints"]["ego"] + " (0) at (0, 0, 0)\n")
        frames = []
        evidence = []
        for row in trace:
            frame, time_s = row["frame"], row["time_s"]
            record = copy.deepcopy(sample)
            record.update(original_frame=frame, replay_frame=frame, actor_id=row["ego"]["actor_id"],
                          recording_time_s=time_s, replay_simulation_time_s=time_s + 13.5)
            record["ego"].update(position_m=row["position_m"], heading_deg=row["heading_deg"],
                                 speed_mps=row["speed_mps"], speed_provenance="synthetic_native_sample")
            x, y, z = row["position_m"]
            length, width, height = row["ego"]["bbox_half_extent_m"]
            body = [[xx, yy, zz] for xx in (x-length, x+length)
                    for yy in (y-width, y+width) for zz in (z-height, z+height)]
            record["ego"]["body_vertices_m"] = body
            record["original_observations"].update(frame=frame, time_s=time_s,
                                                    rgb_sensors=[{"actor_id": 209,
                                                                  "blueprint": "sensor.camera.rgb"}],
                                                    participants=[])
            evidence.append(json.dumps(record, separators=(",", ":"), allow_nan=False) + "\n")
            graph_path = f"graphs/base/{frame}.adapter.json"
            current = copy.deepcopy(small_graph)
            current["metadata"] = {"frame": frame, "simulation_time_s": time_s + 13.5,
                                   "units": graph_template["metadata"]["units"],
                                   "observed_evidence": record["original_observations"]}
            ego_node = current["nodes"][-1]["attributes"]
            heading = math.radians(row["heading_deg"])
            ego_node.update(vertex=row["position_m"], entity_id=row["ego"]["actor_id"],
                            forward=[math.cos(heading), math.sin(heading), 0.],
                            right=[-math.sin(heading), math.cos(heading), 0.],
                            threedbbox=body, carla_speed=row["speed_mps"],
                            carla_vel_x=row["ego"]["velocity_mps"][0],
                            carla_vel_y=row["ego"]["velocity_mps"][1],
                            carla_vel_z=row["ego"]["velocity_mps"][2])
            original = ego_node["original_observation"]
            original.update(actor_id=row["ego"]["actor_id"],
                            blueprint=packet["vehicle_blueprints"]["ego"],
                            position_m=row["position_m"], heading_deg=row["heading_deg"],
                            velocity_mps=row["ego"]["velocity_mps"],
                            speed_mps=row["speed_mps"], body_vertices_m=body)
            files["capture/native/" + graph_path] = json.dumps(current, separators=(",", ":")) + "\n"
            frames.append(json.dumps({"frame": frame, "simulation_time": time_s + 13.5,
                                      "abstract": None, "base": None, "nodes": 4, "edges": 7,
                                      "extraction_seconds": 0., "capture_seconds": 0.,
                                      "adapter_graph": graph_path},
                                     separators=(",", ":")) + "\n")
        files["capture/evidence.jsonl"] = "".join(evidence)
        files["capture/native/frames.jsonl"] = "".join(frames)
        facts = template["files"]["capture/native_map_facts.json"]
        files["capture/native_map_facts.json"] = facts
        manifest = json.loads(template["files"]["capture/manifest.json"])
        manifest["case_id"] = fixture.case_id
        manifest["frames"] = 900
        manifest["source_run"] = "synthetic:crossing-compatibility"
        manifest["sources"] = {name: hashlib.sha256(files[name].encode()).hexdigest()
                               for name in ("road.xodr", "trace.jsonl")}
        manifest["native_map_facts"]["sha256"] = hashlib.sha256(facts.encode()).hexdigest()
        files["capture/manifest.json"] = json.dumps(manifest, separators=(",", ":")) + "\n"
        sources = []
        for path, content in files.items():
            source = source_root / path
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(content)
            if source.stat().st_size > 2 * 1024 * 1024:
                raise ValueError(f"Returned source exceeds 2 MiB: {source}")
            sources.append({"path": path, "source": source.relative_to(root).as_posix(),
                            "sha256": digest(source)})
        specification = {"files": {}, "graphs": [], "videos": [
            {"path": name + ".mkv", "frames": 900, "width": width, "height": height,
             "fps": 20, "color": "blue"}
            for name, width, height in (("overview", 1920, 1080), ("approach", 1280, 720),
                                        ("reference_corner", 1280, 720),
                                        ("driver_reference", 1280, 720))]}
        spec_path = folder / ("diagnostic-" + suffix + ".json")
        spec_path.write_text(json.dumps(specification, separators=(",", ":")) + "\n")
        recipe = {"format": "worker-fixture-recipe", "sources": sources,
                  "generator": {"source": spec_path.relative_to(root).as_posix(),
                                "sha256": digest(spec_path)}}
        (folder / ("diagnostic-" + suffix + "-recipe.json")).write_text(
            json.dumps(recipe, indent=2) + "\n")
        print(suffix, len(files), len(evidence), max((source_root / s["path"]).stat().st_size
                                                   for s in sources))
    finally:
        fixture.doCleanups()
