"""Create explicitly synthetic taxi source joins for CPU finalizer tests."""

from __future__ import annotations

import hashlib
import json
import subprocess
import copy
from pathlib import Path

from analysis import trace_row

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
SIZES = {"overview": (1920,1080), "approach": (1280,720),
         "reference_corner": (1280,720), "driver_reference": (1280,720)}


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prototype_video(view: str) -> str:
    scratch = ROOT.parents[1] / ".runtime-work/c378245-taxi/prototype-videos"
    scratch.mkdir(parents=True, exist_ok=True)
    path = scratch / (view + ".mkv")
    if not path.exists():
        width, height = SIZES[view]
        subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                        "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r=20",
                        "-frames:v", "900", "-an", "-c:v", "ffv1", "-threads", "1",
                        "-fflags", "+bitexact", "-flags:v", "+bitexact", str(path)],
                       check=True, timeout=120)
    return sha(path)


def build() -> None:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    for case in plan["cases"]:
        case_id = case["case_id"]
        suffix = case_id.split("__")[-1]
        root = ROOT / "cases" / suffix / "diagnostic-sources"
        root.mkdir(parents=True, exist_ok=True)
        inside = case["location_request"] == "in_stand"
        x = -55.0 if inside else -20.0
        y = -4.5
        recording = "synthetic-diagnostic-" + suffix
        road_template = (ROOT.parent / "testing__C150530__LVMC-11-60-090__taxi_driver" /
                         "cases/near_stand/diagnostic-sources/road.xodr")
        road_path = root / "road.xodr"
        road_path.write_text(road_template.read_text().replace("C150530", "C378245"))
        map_hash = sha(road_path)
        site = {"source_kind": "synthetic_independent_site_review", "cell_id": "C378245",
                "business_district": True, "street_public_access": True,
                "jurisdiction_review_id": "synthetic-jurisdiction", "map_sha256": map_hash,
                "designation_id": "synthetic-stand", "other_regulation_review_id": "synthetic-rules",
                "stand_polygon_xy_m": [[-60,-8],[-50,-8],[-50,0],[-60,0]],
                "street_polygon_xy_m": [[-90,-10],[20,-10],[20,10],[-90,10]]}
        native = {"source_kind": "synthetic_native", "case_id": case_id,
                  "recording_id": recording, "map_sha256": map_hash,
                  "taxi_vehicle_id": "synthetic-taxi", "operator_id": "synthetic-driver",
                  "frame_count": 900}
        frames = [{"frame": i, "elapsed_s": i/20,
                   "taxi_center_xy_m": [x,y],
                   "taxi_footprint_xy_m": [[x-1,y-1],[x+1,y-1],[x+1,y+1],[x-1,y+1]],
                   "taxi_speed_mps": 0.0} for i in range(900)]
        docs = {"reviewed_site.json": site, "native_result.json": native,
                "native_frames.json": frames,
                "stand_designation.json": {"designation_id": "synthetic-stand", "authority_reviewed": True},
                "taxi_licence.json": {"vehicle_id": "synthetic-taxi", "operator_id": "synthetic-driver"},
                "other_regulations.json": {"review_id": "synthetic-rules",
                                           "legal_compliance_assessed": False}}
        for name, content in docs.items():
            write(root / name, content)
        frame_map = [{"video_frame": i, "carla_frame": i,
                      "native_frame": i, "time_s": i/20} for i in range(900)]
        (root / "video_frames.jsonl").write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in frame_map))
        trace_text = "".join(json.dumps(trace_row(i, row), sort_keys=True) + "\n"
                             for i, row in enumerate(frames))
        template_root = road_template.parent
        event_template = json.loads((template_root / "capture/evidence.jsonl").read_text().splitlines()[0])
        events = []
        graph_frames = []
        graphs = []
        for i, row in enumerate(frames):
            time_s = row["elapsed_s"]
            event = copy.deepcopy(event_template)
            event.update(original_frame=i, replay_frame=i, actor_id=205,
                         recording_time_s=time_s, replay_simulation_time_s=time_s)
            body = [[point[0], point[1], z] for point in row["taxi_footprint_xy_m"]
                    for z in (0.0,1.5)]
            event["ego"].update(position_m=[x,y,0.0], heading_deg=0.0,
                                speed_mps=0.0, speed_provenance="synthetic_native_sample",
                                body_vertices_m=body)
            event["original_observations"].update(frame=i,time_s=time_s)
            events.append(event)
            graph_path = f"capture/native/graphs/base/{i:08d}.adapter.json"
            graph_frames.append({"frame": i, "simulation_time": time_s,
                                 "abstract": None, "base": None, "nodes": 0,
                                 "edges": 0, "extraction_seconds": 0.0,
                                 "capture_seconds": 0.0,
                                 "adapter_graph": f"graphs/base/{i:08d}.adapter.json"})
            graphs.append({"path": graph_path,
                           "attributes": {"frame": i, "simulation_time_s": time_s,
                                          "observed_evidence": event["original_observations"]},
                           "nodes": [], "edges": []})
        capture = root / "capture"
        (capture / "native").mkdir(parents=True,exist_ok=True)
        (capture / "evidence.jsonl").write_text(
            "".join(json.dumps(event, separators=(",", ":"), sort_keys=True) + "\n" for event in events))
        (capture / "native/frames.jsonl").write_text(
            "".join(json.dumps(row, separators=(",", ":"), sort_keys=True) + "\n" for row in graph_frames))
        (capture / "recorder_info.txt").write_text(
            "Version: 1\nMap: OpenDriveMap\n Create 205: vehicle.tesla.model3 (0) at (0, 0, 0)\n")
        (root / "carla_recorder.log").write_text("Synthetic diagnostic recorder identity for " + suffix + "\n")
        map_facts_path = capture / "native_map_facts.json"
        write(map_facts_path, {"map": "Carla/Maps/OpenDriveMap", "junctions": [],
                               "crosswalk_vertices_m": [],
                               "crosswalk_inventory_scope": "synthetic diagnostic map inventory"})
        manifest = {"status": "draft", "acquisition": "synthetic_fixture",
                    "case_id": case_id, "source_run": "synthetic C378245 CPU fixture",
                    "map": "Carla/Maps/OpenDriveMap", "frames": 900,
                    "required_observations": [], "extraction_confirmed": True,
                    "complete_driving_lanes": True, "observation_contract_version": 2,
                    "road_user_visibility_observed": False,
                    "speed_source": "synthetic Native sample",
                    "frame_join": "same synthetic diagnostic frame",
                    "visibility_scope": "diagnostic only",
                    "native_map_facts": {"path": "native_map_facts.json",
                                         "sha256": sha(map_facts_path)},
                    "sources": {"road.xodr": map_hash,
                                "trace.jsonl": hashlib.sha256(trace_text.encode()).hexdigest(),
                                "carla_recorder.log": sha(root / "carla_recorder.log")}}
        write(capture / "manifest.json", manifest)
        for stale in root.glob("camera-source-*.txt"):
            stale.unlink()
        camera_refs = {view: {"path": view + ".mkv", "sha256": prototype_video(view)}
                       for view in VIEWS}
        event = case["passenger_exchange_request"]
        kinds = {"loading": "boarding", "unloading": "alighting"}
        activity = {"source_kind": "synthetic_independent_activity_review",
                    "recording_id": recording, "case_id": case_id,
                    "camera_sha256": {view: camera_refs[view]["sha256"] for view in VIEWS},
                    "halt_interval_frames": [100,799], "activity": case["halt_activity_request"],
                    "reviewer_id": "synthetic-fixture-reviewer",
                    "passenger_events": ([{"kind": kinds[event], "frame": 400,
                                           "passenger_actor_id": "synthetic-passenger",
                                           "observed": True}] if event in kinds else [])}
        write(root / "activity_review.json", activity)
        source_names = {"reviewed_site": "reviewed_site.json",
                        "native_result": "native_result.json", "native_frames": "native_frames.json",
                        "activity_review": "activity_review.json",
                        "stand_designation": "stand_designation.json",
                        "taxi_licence": "taxi_licence.json",
                        "other_regulations": "other_regulations.json"}
        packet = {"assignment_id": ASSIGNMENT, "cell_id": "C378245",
                  "law_id": "LVMC-11-60-040", "actor": "taxi_driver",
                  "case_id": case_id, "recording_id": recording,
                  "diagnostic_fixture": True,
                  "camera_sources": camera_refs}
        packet.update({key: {"path": name, "sha256": sha(root / name)}
                       for key, name in source_names.items()})
        write(root / "taxi-source-packet.json", packet)
        listed = sorted(root.rglob("*"))
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": str(path.relative_to(root)),
                               "source": str(path.relative_to(ROOT.parent.parent)),
                               "sha256": sha(path)} for path in listed if path.is_file()]}
        videos = [{"path": view + ".mkv", "frames": 900, "width": SIZES[view][0],
                   "height": SIZES[view][1], "fps": 20, "color": "black"} for view in VIEWS]
        spec = {"files": {}, "graphs": graphs, "videos": videos}
        spec_path = ROOT / "cases" / suffix / "diagnostic.json"
        write(spec_path, spec)
        recipe["generator"] = {"source": str(spec_path.relative_to(ROOT.parent.parent)),
                               "sha256": sha(spec_path)}
        write(ROOT / "cases" / suffix / "fixture-recipe.json", recipe)
    print("six explicitly synthetic taxi source recipes built")


if __name__ == "__main__":
    build()
