"""Generate synthetic Native-shaped fixtures and exercise exact portable packages."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import pickle
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "native"))
sys.path.insert(0, str(ROOT / "runtime/pipeline/scenario_pipeline"))
from geometry import body, road_xml, STOP_X
from traffic_spec_adapter.adapter import load_graph
from worker_exchange.package_compatibility import run, materialize_case
from worker_exchange.runtime_cli import execution_env


def write_rows(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, allow_nan=False) + "\n" for row in rows))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(destination: Path, suffix: str):
    destination.mkdir()
    (destination / "capture").mkdir()
    construction = json.loads((HERE / "draft-candidates" / suffix / "primary" / "construction.json").read_text())
    config = json.loads(next(f["content"] for f in construction["files"] if f["path"] == "config.json"))
    survey = {"native_map_sha256": "a" * 64,
              "road_directions_native": {"approach_forward": [1, 0],
                                          "approach_opposing": [-1, 0],
                                          "destination_forward": [1, 0],
                                          "destination_opposing": [-1, 0]},
              "approach_centerline_point_native_m": [0, 0],
              "intersection_entry_point_native_m": [-7, 0],
              "intersection_polygon_xy_m": [[-7, -7], [7, -7], [7, 7], [-7, 7]],
              "native_signal_count": 0}
    (destination / "road_geometry.json").write_text(json.dumps(survey))
    (destination / "context.json").write_text(json.dumps({"surveyed_intersection": survey}))
    trace = []; evidence = []; mapping = []; motion = []; history = []; frames = []
    graph = load_graph(ROOT / "runtime/pipeline/fixtures/retained-speed/capture/native/graphs/base/00021714.pkl")
    graph_dir = destination / "capture/native/graphs/base"; graph_dir.mkdir(parents=True)
    stop = STOP_X[suffix]
    for i in range(480):
        frame = 100 + i; time_s = .05 * (i + 1)
        fraction = min(i / 239, 1.0)
        x = round(-50 + (stop + 50) * fraction, 5); y = -1.75
        corners = body(x, y)
        vertices = [[a, b, z] for a, b in corners for z in (0, 1.5)]
        speed = 4.0 if i < 240 else 0.0
        sample = {"native_frame": frame, "time_s": time_s,
                  "native_center_xy_m": [x, y], "native_forward_xy": [1, 0],
                  "native_body_xy_m": corners, "body_xy_m": corners,
                  "video_frame": i, "speed_m_s": speed,
                  "native_intersection_survey": True,
                  "exception_source": {"other_traffic_actor_count": 0,
                                       "native_signal_count": 0,
                                       "authored_law_direction_count": 0},
                  "exceptions": {"traffic_conflict": False,
                                 "lawful_direction": False,
                                 "police_direction": False,
                                 "traffic_device": False}}
        motion.append(sample)
        mapping.append({"video_frame": i, "native_frame": frame,
                        "carla_frame": frame, "time_s": time_s})
        history.append({"frame": frame, "time_s": time_s,
                        "body_vertices_m": vertices})
        trace.append({"frame": frame, "time_s": time_s,
                      "position": {"x": x, "y": y, "z": .5},
                      "position_m": [x, y, .5], "heading_deg": 0,
                      "speed_mps": speed, "speed_mph": speed / .44704,
                      "control": {"throttle": 0, "brake": 0, "hand_brake": False}})
        road = 1 if x < -7 else 13 if x < 7 else 2
        evidence.append({"original_frame": frame, "recording_time_s": time_s,
                         "replay_frame": frame, "replay_simulation_time_s": time_s,
                         "actor_id": 107,
                         "ego": {"body_vertices_m": vertices,
                                 "position_m": [x, y, .5], "heading_deg": 0,
                                 "speed_mps": speed,
                                 "speed_provenance": "original_trace_actor_get_velocity"},
                         "world": {"weather": {"cloudiness": 0, "precipitation": 0,
                                               "wetness": 0, "fog_density": 0},
                                   "road_projection": {"road_id": road,
                                                       "section_id": 0, "lane_id": -1,
                                                       "s_m": x + 100}}})
        graph.graph["frame"] = frame
        (graph_dir / f"{frame:08d}.pkl").write_bytes(pickle.dumps(graph, protocol=4))
        frames.append({"frame": frame, "simulation_time": time_s,
                       "time_s": time_s,
                       "base": f"graphs/base/{frame:08d}.pkl",
                       "abstract": f"graphs/abstract/{frame:08d}.pkl",
                       "synthetic_diagnostic": True})
    for name, rows in (("trace.jsonl", trace), ("capture/evidence.jsonl", evidence),
                       ("video_frames.jsonl", mapping), ("native_samples.jsonl", motion),
                       ("body_history.jsonl", history), ("capture/native/frames.jsonl", frames)):
        write_rows(destination / name, rows)
    (destination / "capture/recorder_info.txt").write_text("Create 107: vehicle.lincoln.mkz_2020\n")
    (destination / "capture/manifest.json").write_text(json.dumps({
        "extraction_confirmed": True, "frames": 480,
        "sources": {"road.xodr": sha(HERE / "native/road.xodr"),
                    "trace.jsonl": sha(destination / "trace.jsonl")},
        "synthetic_diagnostic": True}))
    (destination / "channels").mkdir()
    for channel in config["recording_description"]["channels"]:
        name = channel["name"]
        values = []
        for i, sample in enumerate(motion):
            speed = sample["speed_m_s"]
            mapping_row = mapping[i]
            by_name = {"drv.standing_or_parked": {"speed_m_s": speed},
                       "st.intersection": survey,
                       "rel.occupies": {"body_xy_m": sample["body_xy_m"],
                                        "intersection_polygon_xy_m": survey["intersection_polygon_xy_m"]},
                       "drv.forced_halt": {"traffic_conflict": False,
                                           "exclusive_world_actor_count": 1},
                       "dev.human_direction": {"police_direction": False,
                                               "exclusive_world_actor_count": 1},
                       "dev.traffic_signal": {"traffic_device": False,
                                              "native_signal_count": 0},
                       "kin.velocity": {"speed_m_s": speed},
                       "native_body_pose_control": sample,
                       "camera_frame_join": mapping_row}
            values.append({"time_s": sample["time_s"], "value": by_name[name]})
        write_rows(destination / "channels" / (name + ".jsonl"), values)
    for camera in config["cameras"]:
        size = f"{camera['width']}x{camera['height']}"
        subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                        "-f", "lavfi", "-i", f"color=c=black:s={size}:r=20:d=24",
                        "-frames:v", "480", "-c:v", "ffv1",
                        str(destination / (camera["name"] + ".mkv"))],
                       check=True, timeout=120)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suffix", choices=("probe_a", "probe_b"), required=True)
    parser.add_argument("--candidate", choices=("primary", "fallback1", "fallback2", "fallback3"),
                        default="primary")
    parser.add_argument("--fixture-only", action="store_true")
    parser.add_argument("--reuse-fixture", type=Path)
    args = parser.parse_args()
    scratch = Path(tempfile.mkdtemp(dir=ROOT / ".runtime-work", prefix="c110454-450-1c-portable-"))
    source = args.reuse_fixture.resolve() if args.reuse_fixture else scratch / "fixture"
    if not args.reuse_fixture: fixture(source, args.suffix)
    if not source.is_dir(): raise ValueError("Reusable synthetic source fixture absent")
    if args.fixture_only:
        print(json.dumps({"fixture": str(source), "scope": "synthetic Native-shaped CPU only"}))
        return
    case = HERE.name + "__" + args.suffix
    output = scratch / "output"
    print("scratch", scratch, flush=True)
    receipt = run(HERE / "draft-execution-manifest.json", case, source, output,
                  ROOT / "runtime/pipeline/library",
                  ROOT / ".runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck",
                  args.candidate)
    negative = scratch / "negative"
    materialize_case(HERE / "draft-execution-manifest.json", case, negative, source, args.candidate)
    (negative / "native_samples.jsonl").unlink()
    failed = subprocess.run([sys.executable, str(negative / "finalize.py"), "--attempt", str(negative),
                             "--output", str(negative / "analysis-report.json")], cwd=negative,
                            env=execution_env(), text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=300)
    expected = "Missing required source: native_samples.jsonl"
    if failed.returncode == 0 or expected not in failed.stdout:
        raise RuntimeError("Negative exact package did not reject removed Native source: " + failed.stdout)
    proof = {"case_suffix": args.suffix, "candidate": args.candidate,
             "positive": {k: v for k, v in receipt.items() if k != "fixture_manifest"},
             "negative": {"exit_code": failed.returncode,
                          "removed": "native_samples.jsonl", "error_contains": expected,
                          "log_sha256": hashlib.sha256(failed.stdout.encode()).hexdigest()},
             "scratch": str(scratch), "fixture": str(source),
             "scope": "synthetic diagnostic portable package; no CARLA or acceptance"}
    label = args.suffix + "-" + args.candidate
    (HERE / ("portable-proof-" + label + ".json")).write_text(json.dumps(proof, indent=2) + "\n")
    shutil.copyfile(output / "compatibility-analysis.log", HERE / ("portable-analysis-" + label + ".log"))
    (HERE / ("portable-negative-" + label + ".log")).write_text(failed.stdout)
    print(json.dumps(proof))


if __name__ == "__main__": main()
