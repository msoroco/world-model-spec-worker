"""Twenty-frame diagnostic test of the full independent delivery audit path."""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
from worker_exchange.media import compose_four_views
from delivery_audit import CAMERAS, audit, sha


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def jsonlines(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, allow_nan=False, separators=(",", ":")) + "\n" for row in rows))


def build(case_id, root):
    if root.exists():
        raise ValueError("Use a fresh diagnostic audit root")
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    entry = next(e for e in manifest["cases"] if e["case_id"] == case_id)
    construction = json.loads((HERE / entry["construction"]).read_text())
    config = json.loads(next(f["content"] for f in construction["files"] if f["path"] == "config.json"))
    recipe = json.loads((ROOT / entry["fixture_recipe"]).read_text())
    sources = {item["path"]: ROOT / item["source"] for item in recipe["sources"]}
    attempt = root / "attempt"
    attempt.mkdir(parents=True)
    for item in construction["files"]:
        if item["path"].endswith(".py"):
            target = attempt / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item["content"])
    config["duration_s"] = 1
    write(attempt / "config.json", config)
    site = config["site_source"]["path"]
    site_file = next(f for f in construction["files"] if f["path"] == site)
    (attempt / site).write_text(site_file["content"])
    if sha(attempt / site) != config["site_source"]["sha256"]:
        raise ValueError("Embedded diagnostic site changed")
    write(attempt / "acquisition-provenance.json", {"provenance_kind": "synthetic_fixture",
                                                 "diagnostic_fixture": True,
                                                 "scope": "Twenty-frame software test, not physical acquisition"})
    names = ("video_frames.jsonl", "motion_history.jsonl", "trace.jsonl",
             "capture/evidence.jsonl", "turn_history.jsonl")
    indices = [round(index * 1099 / 19) for index in range(20)]
    streams = {}
    for name in names:
        original = [json.loads(line) for line in sources[name].read_text().splitlines() if line.strip()]
        if len(original) != 1100:
            raise ValueError("Diagnostic source duration changed: " + name)
        streams[name] = [copy.deepcopy(original[i]) for i in indices]
    for index in range(20):
        frame_number, time_s = 1000 + index, index / config["rate_hz"]
        frame = streams["video_frames.jsonl"][index]
        frame.update(video_frame=index, carla_frame=frame_number, native_frame=frame_number, time_s=time_s)
        motion = streams["motion_history.jsonl"][index]
        motion.update(video_frame=index, native_frame=frame_number)
        motion["ego"]["id"] = 101
        for offset, direction in enumerate(("approach_a", "approach_b"), start=2):
            motion["approaches"][direction]["id"] = 100 + offset
        trace = streams["trace.jsonl"][index]
        trace.update(frame=frame_number, time_s=time_s)
        turn = streams["turn_history.jsonl"][index]
        turn.update(frame=frame_number, time_s=time_s)
        capture = streams["capture/evidence.jsonl"][index]
        capture.update(original_frame=frame_number, replay_frame=frame_number,
                       recording_time_s=time_s, replay_simulation_time_s=time_s)
        observation = capture["original_observations"]
        observation.update(frame=frame_number, time_s=time_s)
        ego = observation["participants"][0]
        ego["actor_id"] = 101
        for offset, direction in enumerate(("approach_a", "approach_b"), start=2):
            actor = motion["approaches"][direction]
            other = copy.deepcopy(ego)
            other.update(actor_id=100 + offset, position_m=actor["location_xyz_m"],
                         velocity_mps=actor["velocity_xyz_mps"])
            observation["participants"].append(other)
    for name in names:
        jsonlines(attempt / name, streams[name])
    (attempt / "curve_context.json").write_bytes(sources["curve_context.json"].read_bytes())
    write(attempt / "converted/trace.json", {"scenes": [{"t": round(row["time_s"] * 1000)}
                                                   for row in streams["video_frames.jsonl"]]})
    dimensions = {"overview": (1920, 1080), "approach": (1280, 720),
                  "reference_corner": (1280, 720), "driver_reference": (1280, 720)}
    for name, (width, height) in dimensions.items():
        subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                        "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r=20",
                        "-vf", "drawbox=x=20:y=20:w=64:h=64:color=red:t=fill",
                        "-frames:v", "20", "-c:v", "ffv1", "-pix_fmt", "yuv444p",
                        str(attempt / (name + ".mkv"))], check=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "runtime/scenario_pipeline") + os.pathsep + env.get("PYTHONPATH", "")
    subprocess.run([sys.executable, str(attempt / "finalizer.py"), "--attempt", str(attempt),
                    "--output", str(attempt / "analysis-report.json")], cwd=attempt, env=env, check=True)
    result = json.loads((attempt / "result.json").read_text())
    if (result["physical_checks"]["maneuver"]["status"] != "met" or
            result["physical_checks"]["target"]["status"] != "met"):
        raise ValueError("Pinned diagnostic turn and sight target did not complete")
    compose_four_views({name: attempt / (name + ".mkv") for name in CAMERAS},
                       attempt / "video_frames.jsonl", attempt / "raw.mkv")
    sealed = {name: sha(attempt / name) for name in ("config.json", *names, *
        (camera + ".mkv" for camera in CAMERAS))}
    write(attempt / "capture-seal.json", {"format": "worker-sealed-capture",
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "frames": 20, "sources": sealed,
            "events": ["capture_finished", "encoders_closed", "restoration_verified"],
            "physical_acceptance_claimed": False})
    write(attempt / "native-exit.json", {"event": "native_exit",
                                            "capture_seal_sha256": sha(attempt / "capture-seal.json")})
    write(attempt / "owner-release.json", {"event": "owner_released", "operator_attested": True,
                                             "native_exit_sha256": sha(attempt / "native-exit.json")})
    actor_ids = [row["actor_id"] for row in streams["capture/evidence.jsonl"][0]
                 ["original_observations"]["participants"]]
    review = {"case_id": case_id, "reviewer": "diagnostic CPU generator",
              "method": "Colored fixture pixels only; no real actor visibility assertion",
              "frame_map_sha256": sha(attempt / "video_frames.jsonl"),
              "source_sha256": {name: sha(attempt / (name + ".mkv")) for name in CAMERAS},
              "observations": [{"camera": camera, "video_frame": 0, "actor_id": ident,
                                "bbox_xyxy": [16, 16, 100, 100]}
                               for camera in CAMERAS for ident in actor_ids]}
    write(root / "pixel-review.json", review)
    return attempt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--negative-missing-source", action="store_true")
    parser.add_argument("--negative-source-root", type=Path)
    args = parser.parse_args()
    root = args.output_root.resolve()
    if args.negative_source_root:
        source = args.negative_source_root.resolve()
        if root.exists() or not (source / "attempt/diagnostic-audit.json").is_file() or not args.negative_missing_source:
            raise ValueError("Fresh negative root and positive diagnostic audit required")
        shutil.copytree(source, root, copy_function=os.link)
        attempt = root / "attempt"
        (attempt / "capture/evidence.jsonl").unlink()
    else:
        attempt = build(args.case, root)
        if args.negative_missing_source:
            (attempt / "capture/evidence.jsonl").unlink()
    report = audit(attempt, args.case, "diagnostic-job", 1, "diagnostic-recording",
                   root / "pixel-review.json", attempt / "diagnostic-audit.json",
                   root / "source-decode.json", diagnostic_selftest=True)
    if report["passed"] or not report["software_checks_passed"] or not report["diagnostic_fixture"]:
        raise ValueError("Diagnostic audit claimed physical delivery")
    print(json.dumps({"case_id": args.case, "software_checks_passed": True,
                      "physical_acceptance_claimed": False,
                      "diagnostic_audit_sha256": sha(attempt / "diagnostic-audit.json")}))


if __name__ == "__main__":
    main()
