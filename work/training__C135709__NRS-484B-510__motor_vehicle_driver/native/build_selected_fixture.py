"""Build explicit synthetic source-shape fixtures for selected CPU diagnostics.

These packets exercise saved software paths only. They are never Native evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from capture_plan import AID, CAMERAS, CASES
from geometry import SIGN_NAME, open_drive
from original_source_contract import REVIEW_FINDINGS

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
VIDEOS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCE_NAMES = ("acquisition-provenance.json", "capture-manifest.json",
                "road.xodr", "zone-survey.json", "actor-frames.jsonl",
                "camera-frames.jsonl", "trace.jsonl", "video_frames.jsonl",
                "capture/evidence.jsonl", "capture/manifest.json",
                "capture/native/frames.jsonl", "capture/recorder_info.txt")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def lines(path: Path, values) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in values) + "\n")


def build(suffix: str) -> dict:
    if suffix not in CASES:
        raise ValueError("exact case required")
    scratch = REPO / ".runtime-work"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="c135709-fixture-", dir=scratch) as temporary:
        stage = Path(temporary)
        spec = {"files": {}, "graphs": [], "videos": []}
        for camera in VIDEOS:
            width, height = CAMERAS[camera]
            spec["videos"].append({"path": camera + ".mkv", "frames": 600,
                                   "width": width, "height": height, "fps": 20,
                                   "color": {"overview": "blue", "approach": "green",
                                             "reference_corner": "white",
                                             "driver_reference": "red"}[camera]})
            subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                            "-f", "lavfi", "-i", f"color=c={spec['videos'][-1]['color']}:s={width}x{height}:r=20",
                            "-frames:v", "600", "-an", "-c:v", "ffv1", "-threads", "1",
                            "-fflags", "+bitexact", "-flags:v", "+bitexact",
                            str(stage / (camera + ".mkv"))], check=True, timeout=120)
        case_id = AID + "__" + suffix
        (stage / "road.xodr").write_text(open_drive())
        map_sha = sha(stage / "road.xodr")
        write(stage / "acquisition-provenance.json",
              {"provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
               "physical_acceptance_claimed": False})
        write(stage / "zone-survey.json", {"bounds_m": [0.0, -4.0, 10.0, -1.0],
              "map_sha256": map_sha, "sign_id": "510", "sign_text_readback": SIGN_NAME,
              "sign_authority": "unverified", "sign_pixels": "unverified"})
        departure = CASES[suffix].get("departure_frame")
        passenger_request = CASES[suffix]["passenger_exchange_request"]
        waiting_request = CASES[suffix]["waiting_vehicle_request"]
        actors, joins, trace, frame_map, evidence, native_frames = [], [], [], [], [], []
        for i in range(600):
            frame, time_s = 100 + i, i / 20
            x = 5.0 + max(0, i - departure) * .05 if departure is not None else 5.0
            moving = departure is not None and i > departure
            box = [x - 2, -3.5, x + 2, -1.5]
            center_x = (box[0] + box[2]) / 2
            actors.append({"frame": i, "native_frame": frame, "elapsed_s": time_s,
                           "ego_body_m": box, "ego_speed_mps": 1.0 if moving else 0.0,
                           "departure_requested": departure is not None and i >= departure,
                           "passenger_actor_ids_near_vehicle": ([8] if passenger_request and i >= 100 else []),
                           "door_open_request": passenger_request and 95 <= i <= 105,
                           "other_vehicles": ([{"actor_id": 91, "body_m": [8, -3.5, 12, -1.5],
                                                "speed_mps": 0.0, "requesting_zone_entry": True}]
                                              if waiting_request and 200 <= i < 210 else [])})
            joins.append({"frame": i, "native_frame": frame,
                          "cameras": {name: i for name in VIDEOS}})
            trace.append({"frame": frame, "time_s": time_s,
                          "position_m": [center_x, -2.5],
                          "position": {"x": x, "y": -2.5, "z": 1.0},
                          "heading_deg": 0.0, "velocity_mps": [1.0 if moving else 0.0, 0.0, 0.0],
                          "control": {"throttle": 0.35 if moving else 0.0,
                                      "brake": 0.0 if moving else 1.0,
                                      "hand_brake": False},
                          "speed_mps": 1.0 if moving else 0.0,
                          "speed_mph": (1.0 if moving else 0.0) / 0.44704})
            frame_map.append({"video_frame": i, "carla_frame": frame,
                              "native_frame": frame, "time_s": time_s,
                              "camera_native_frames": {name: frame for name in VIDEOS}})
            vertices = [[xx, yy, zz] for xx in (box[0], box[2])
                        for yy in (box[1], box[3]) for zz in (0.0, 1.5)]
            evidence.append({"original_frame": frame, "replay_frame": frame,
                             "actor_id": 7, "recording_time_s": time_s,
                             "replay_simulation_time_s": time_s,
                             "ego": {"position_m": [x, -2.5, 1.0],
                                     "heading_deg": 0.0, "speed_mps": 1.0 if moving else 0.0,
                                     "speed_provenance": "synthetic_native_sample",
                                     "body_vertices_m": vertices},
                             "world": {"weather": {"cloudiness": 0, "precipitation": 0,
                                                   "wetness": 0, "fog_density": 0},
                                       "road_projection": {"road_id": 1, "section_id": 0,
                                                           "lane_id": -1, "s_m": x}}})
            graph_path = f"capture/native/graphs/base/{frame:08d}.adapter.json"
            native_frames.append({"frame": frame, "time_s": time_s,
                                  "simulation_time": time_s,
                                  "synthetic_diagnostic": True,
                                  "adapter_graph": f"graphs/base/{frame:08d}.adapter.json"})
            spec["graphs"].append({"path": graph_path, "attributes": {"frame": frame},
                                   "nodes": [], "edges": []})
        for name, rows in (("actor-frames.jsonl", actors), ("camera-frames.jsonl", joins),
                           ("trace.jsonl", trace), ("video_frames.jsonl", frame_map),
                           ("capture/evidence.jsonl", evidence),
                           ("capture/native/frames.jsonl", native_frames)):
            lines(stage / name, rows)
        write(stage / "capture/manifest.json",
              {"extraction_confirmed": True, "frames": 600,
               "required_observations": [], "synthetic_diagnostic": True,
               "sources": {"road.xodr": map_sha,
                           "trace.jsonl": sha(stage / "trace.jsonl")}})
        (stage / "capture/recorder_info.txt").write_text(
            "Create 7: vehicle.tesla.model3 synthetic diagnostic source-shape fixture\n")
        write(stage / "capture-manifest.json",
              {"source_kind": "synthetic_fixture", "case_id": case_id,
               "frame_count": 600, "fps": 20, "closed": True,
               "world_restored": True, "map_sha256": map_sha,
               "video_sources": {name: {"path": name + ".mkv",
                                        "sha256": sha(stage / (name + ".mkv"))}
                                 for name in VIDEOS}})
        review_names = ("capture-manifest.json", "road.xodr", "zone-survey.json",
                        "actor-frames.jsonl", "camera-frames.jsonl", "trace.jsonl",
                        "video_frames.jsonl") + tuple(name + ".mkv" for name in VIDEOS)
        write(stage / "original-review.json",
              {"case_id": case_id, "source_sha256": {name: sha(stage / name) for name in review_names},
               "reviewer": "synthetic-fixture-protocol", "restricted_purpose": "unverified",
               "sign_authority": "unverified", "sign_pixel_status": "unverified",
               "original_findings": {name: {"status": "unverified", "source_refs": []}
                                     for name in REVIEW_FINDINGS}})
        target = ROOT / "selected-source" / suffix
        target.mkdir(parents=True, exist_ok=True)
        explicit = SOURCE_NAMES + ("original-review.json",)
        for relative in explicit:
            source, destination = stage / relative, target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        spec_path = ROOT / f"selected-generator-{suffix}.json"
        write(spec_path, spec)
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": name,
                               "source": str((target / name).relative_to(REPO)),
                               "sha256": sha(target / name)} for name in explicit],
                  "generator": {"source": str(spec_path.relative_to(REPO)),
                                "sha256": sha(spec_path)}}
        recipe_path = ROOT / f"selected-recipe-{suffix}.json"
        write(recipe_path, recipe)
        return {"case_id": case_id, "recipe": str(recipe_path.relative_to(REPO)),
                "recipe_sha256": sha(recipe_path)}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("suffix", choices=sorted(CASES))
    args = parser.parse_args()
    print(json.dumps(build(args.suffix), sort_keys=True))
