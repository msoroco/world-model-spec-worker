"""Create source-shaped CPU fixtures for four exact center-turn-lane cases.

These synthetic source packets prove software compatibility only. They do not
assert an actual public highway, lane dedication, physical run, or legal result.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
from native_capture import VIEWS, capture_original


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root, relative, value):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded(value))
    return {"path": relative, "sha256": digest(path)}


def site(root):
    return {"native_map_source": source(root, "native/map.json", {"original_opendrive_hash": "synthetic-only"}),
            "highway_review_source": source(root, "review/highway.json", {"public_highway": "synthetic-only"}),
            "public_highway_confirmed": True,
            "lanes": [{"id": "center", "road_id": 42, "center_turn_lane": True, "exclusive_turn_use": True,
                       "permitted_turn_directions": ["negative", "positive"],
                       "centreline_xy_m": [[0, 0], [100, 0]]},
                      {"id": "east", "road_id": 42, "receiving_through": True,
                       "centreline_xy_m": [[0, -3], [100, -3]]},
                      {"id": "west", "road_id": 42, "opposing_through": True,
                       "centreline_xy_m": [[100, 3], [0, 3]]}],
            "entry_maneuver": "left_turn_onto_highway", "entry_target_lane_id": "center",
            "merge_target_lane_id": "east"}


def build():
    scratch = REPO / ".runtime-work/c109749-fixture-build"
    scratch.mkdir(parents=True, exist_ok=True)
    road = json.loads((REPO / "work/testing__C110969__NRS-484B-450-1c__motor_vehicle_driver/cases/inside_stop/diagnostic.json").read_text())["files"]["road.xodr"]
    plan = json.loads((HERE / "case-plan.json").read_text())
    for case in plan["cases"]:
        case_id = case["case_id"]
        suffix = case_id.removeprefix(HERE.name + "__")
        if case_id != HERE.name + "__" + suffix:
            raise ValueError("Foreign exact case")
        folder = HERE / "cases" / suffix
        run = scratch / suffix
        if run.exists():
            shutil.rmtree(run)
        original = run / "original-attempt"
        original.mkdir(parents=True)
        packet = site(original)
        pixel = original / "camera/pixel.png"
        pixel.parent.mkdir()
        pixel.write_bytes(b"diagnostic placeholder; no original pixels")
        desired_ft = case["authored_target_distance_ft"] or 60
        distance_m = desired_ft * 0.3048
        samples = []
        for index in range(900):
            frame = 1000 + index
            merge = index == 899 and suffix != "no_merge"
            samples.append({"frame": frame, "elapsed_seconds": index / 20,
                            "body_centre_xy_m": [max(0, index - 1) * distance_m / 898, 0.0],
                            "lane_id": "approach" if index == 0 else ("east" if merge else "center"),
                            "approach_lane": index == 0,
                            "left_turn_onto_highway_complete": index == 1,
                            "merged_into_through_lane": merge,
                            "receiving_vehicle_actor_id": 17,
                            "camera_sources": {view: "camera/pixel.png" for view in VIEWS}})
        capture_original(original, case_id, packet, samples.__getitem__, 900, first_frame=1000)
        frame_map_path = original / "native/frame_map.json"
        frame_map = json.loads(frame_map_path.read_text())
        for row in frame_map["frames"]:
            del row["camera_sha256"]
        frame_map_path.write_text(encoded(frame_map))
        receipt_path = original / "native/capture-receipt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["frame_map_source"]["sha256"] = digest(frame_map_path)
        receipt_path.write_text(encoded(receipt))
        pixel.unlink()
        source_root = folder / "fixture-sources"
        source_root.mkdir(exist_ok=True)
        inputs = []
        for path in original.rglob("*"):
            if path.is_file():
                relative = "original-attempt/" + str(path.relative_to(original))
                target = source_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())
                inputs.append({"path": relative, "source": str(target.relative_to(REPO)),
                               "sha256": digest(target)})
        trace = []
        mapping = []
        events = []
        frames = []
        graphs = []
        for index, sample in enumerate(samples):
            frame, time_s = sample["frame"], index / 20
            x, y = sample["body_centre_xy_m"]
            trace.append({"frame": frame, "time_s": time_s,
                          "position": {"x": x, "y": y, "z": 0.0},
                          "position_m": [x, y, 0.0], "heading_deg": 0.0,
                          "speed_mps": 0.0, "speed_mph": 0.0,
                          "velocity_mps": [0.0, 0.0, 0.0], "control": {}})
            mapping.append({"video_frame": index, "carla_frame": frame, "time_s": time_s})
            observed = {"frame": frame, "time_s": time_s,
                        "map_context": {"junction_id": 0}, "participants": []}
            events.append({"actor_id": 1, "original_frame": frame, "replay_frame": frame,
                           "recording_time_s": time_s, "replay_simulation_time_s": time_s,
                           "ego": {"position_m": [x, y, 0.0], "heading_deg": 0.0,
                                   "speed_mps": 0.0, "speed_provenance": "synthetic_native_sample",
                                   "body_vertices_m": [[x + dx, y + dy, z]
                                                       for dx in (-2.25, 2.25)
                                                       for dy in (-0.9, 0.9)
                                                       for z in (-0.5, 0.5)]},
                           "world": {"weather": {}}, "original_observations": observed})
            graph_path = f"graphs/base/{frame:08d}.adapter.json"
            frames.append({"frame": frame, "simulation_time": time_s, "adapter_graph": graph_path})
            graphs.append({"path": "capture/native/" + graph_path,
                           "attributes": {"frame": frame, "observed_evidence": observed, "time_s": time_s},
                           "nodes": [], "edges": []})
        generated = {
            "acquisition-provenance.json": encoded({"diagnostic_fixture": True,
                                                    "provenance_kind": "synthetic_fixture"}),
            "fixture-provenance.json": encoded({"diagnostic_fixture": True,
                                                "scope": "CPU software fixture; no original camera pixels"}),
            "road.xodr": road,
            "trace.jsonl": "".join(encoded(row) for row in trace),
            "video_frames.jsonl": "".join(encoded(row) for row in mapping),
            "capture/evidence.jsonl": "".join(encoded(row) for row in events),
            "capture/native/frames.jsonl": "".join(encoded(row) for row in frames),
            "capture/recorder_info.txt": "Create 1: vehicle.synthetic.ego (0) at (0, 0, 0)\n",
        }
        generated["capture/manifest.json"] = encoded({
            "acquisition": "diagnostic_fixture", "case_id": case_id, "frames": 900,
            "extraction_confirmed": True,
            "sources": {"road.xodr": hashlib.sha256(road.encode()).hexdigest(),
                        "trace.jsonl": hashlib.sha256(generated["trace.jsonl"].encode()).hexdigest()},
            "required_observations": [], "status": "draft"})
        videos = [{"path": view + ".mkv", "frames": 900,
                   "width": 1920 if view == "overview" else 1280,
                   "height": 1080 if view == "overview" else 720,
                   "fps": 20, "color": "black"} for view in VIEWS]
        specification = folder / "diagnostic.json"
        specification.write_text(encoded({"files": generated, "graphs": graphs, "videos": videos}))
        recipe = folder / "fixture-recipe.json"
        recipe.write_text(encoded({"format": "worker-fixture-recipe",
                                   "generator": {"source": str(specification.relative_to(REPO)),
                                                 "sha256": digest(specification)},
                                   "sources": sorted(inputs, key=lambda item: item["path"])}))
        if max(specification.stat().st_size, recipe.stat().st_size) > 2 * 1024 * 1024:
            raise ValueError("Returned diagnostic text exceeds file size gate")
        shutil.rmtree(run)
        print(suffix, "diagnostic bytes", specification.stat().st_size)


if __name__ == "__main__":
    build()
