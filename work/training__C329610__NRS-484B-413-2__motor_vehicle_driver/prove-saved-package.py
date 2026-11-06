"""Six 800-frame synthetic saved positives and removed-source negatives."""
import hashlib
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "runtime/pipeline/scenario_pipeline"))
from worker_exchange.measurement_contract import verify_report


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, allow_nan=False) for r in rows) + "\n")


def build(source, suffix, full_resolution=False):
    if source.exists():
        shutil.rmtree(source)
    source.mkdir(parents=True)
    (source / "capture").mkdir()
    construction = json.loads((HERE / "draft-candidates" / suffix / "primary/construction.json").read_text())
    config = json.loads(next(f["content"] for f in construction["files"] if f["path"] == "config.json"))
    (source / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    request = config["native_request"]
    (source / "road_geometry.json").write_text(json.dumps({"native_map_sha256": request["map_sha256"],
        "authored_map_sha256": request["map_sha256"],
        "area_classification": request["area"], "provenance": "synthetic_cpu_fixture"}) + "\n")
    raw = [json.loads(line) for line in (HERE / "signal-fixtures" / (suffix + ".jsonl")).read_text().splitlines()]
    assert len(raw) == 800
    streams = {name: [] for name in ("trace.jsonl", "capture/evidence.jsonl", "video_frames.jsonl",
                                     "native_samples.jsonl", "body_history.jsonl")}
    channels = {c["name"]: [] for c in config["recording_description"]["channels"]}
    for i, row in enumerate(raw):
        frame = 100 + i
        t = (i + 1) / 20
        x, y = row["ego_xy_m"]
        angle = math.radians(row["heading_deg"])
        fx, fy = math.cos(angle), math.sin(angle)
        rx, ry = -fy, fx
        corners = [[x + u * fx + v * rx, y + u * fy + v * ry] for u, v in
                   ((-2.6,-1.1),(-2.6,1.1),(2.6,1.1),(2.6,-1.1))]
        body = [[a,b,z] for a,b in corners for z in (0,1.5)]
        speed = 0.0 if i == 0 else math.dist(raw[i-1]["ego_xy_m"], row["ego_xy_m"]) * 20
        native = dict(row, native_frame=frame, time_s=t, native_center_xy_m=[x,y],
                      native_forward_xy=[fx,fy], native_body_xy_m=corners,
                      speed_mps=speed, light_state_bits=1 if row["signal"] == "left" else 0,
                      left_indicator_state_observed=row["signal"] == "left")
        streams["native_samples.jsonl"].append(native)
        streams["trace.jsonl"].append({"frame":frame,"time_s":t,
            "position":{"x":x,"y":y,"z":.5},"heading_deg":row["heading_deg"],"speed_mps":speed})
        streams["capture/evidence.jsonl"].append({"original_frame":frame,"recording_time_s":t,
            "ego":{"body_vertices_m":body}})
        streams["video_frames.jsonl"].append({"video_frame":i,"native_frame":frame,
            "carla_frame":frame,"time_s":t})
        streams["body_history.jsonl"].append({"frame":frame,"time_s":t,"body_vertices_m":body})
        values = {"sig.turn_indicator":{"observed_left_indicator_state":row["signal"]=="left"},
                  "drv.distance_while":{"signal":row["signal"],"xy_m":[x,y]},
                  "kin.path_length":{"xy_m":[x,y]},"drv.turning":{"heading_deg":row["heading_deg"]},
                  "env.precipitation":row["weather"],"kin.speed":speed,
                  "native_body_pose_control":native,"camera_frame_join":streams["video_frames.jsonl"][-1]}
        for name in channels:
            channels[name].append({"time_s":t,"value":values[name]})
    for name, rows in streams.items():
        write_rows(source / name, rows)
    (source / "capture/manifest.json").write_text(json.dumps({"extraction_confirmed":True,"frames":800}) + "\n")
    for name, rows in channels.items():
        write_rows(source / "channels" / (name + ".jsonl"), rows)
    sizes={c['name']:f"{c['width']}x{c['height']}" for c in config['cameras']}
    for name in ("overview", "approach", "reference_corner", "driver_reference"):
        size=sizes[name] if full_resolution else '32x32'
        subprocess.run(["ffmpeg","-nostdin","-hide_banner","-loglevel","error","-y",
            "-f","lavfi","-i",f"color=c=black:s={size}:r=20:d=40","-frames:v","800",
            "-c:v","ffv1",str(source / (name + ".mkv"))],check=True,timeout=120)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--full-resolution',action='store_true')
    parser.add_argument('--suffix',choices=("below_100_ft","at_100_ft","above_100_ft",
                                           "below_300_ft","at_300_ft","above_300_ft"))
    args=parser.parse_args()
    out = REPO / ".runtime-work" / ("c329610-413-saved-fixtures-full" if args.full_resolution
                                    else "c329610-413-saved-fixtures")
    out.mkdir(exist_ok=True)
    manifest = json.loads((HERE / "draft-execution-manifest.json").read_text())
    records = []
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join((str(REPO / "runtime/pipeline/scenario_pipeline"),
        str(REPO / "runtime/pipeline/python"), str(REPO / "runtime/pipeline"), env.get("PYTHONPATH", "")))
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        if args.suffix and suffix!=args.suffix:
            continue
        source = out / (suffix + "-source")
        build(source, suffix, full_resolution=args.full_resolution)
        positive = out / (suffix + "-positive")
        negative = out / (suffix + "-negative")
        for path in (positive, negative):
            if path.exists():
                shutil.rmtree(path)
            shutil.copytree(source, path)
        command = [sys.executable, str(HERE / "native/finalize.py"),
                   "--attempt", str(positive), "--output", str(positive / "analysis-report.json")]
        ok = subprocess.run(command, cwd=REPO, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
        if ok.returncode:
            raise RuntimeError(suffix + " positive: " + ok.stdout[-1500:])
        report = json.loads((positive / "analysis-report.json").read_text())
        contract = json.loads((HERE / entry["measurement_contract"]).read_text())
        verify_report(contract, report, positive)
        (negative / "native_samples.jsonl").unlink()
        bad = subprocess.run([sys.executable, str(HERE / "native/finalize.py"),
            "--attempt", str(negative), "--output", str(negative / "analysis-report.json")],
            cwd=REPO, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
        if bad.returncode == 0 or "Missing required source: native_samples.jsonl" not in bad.stdout:
            raise RuntimeError(suffix + " negative failed: " + bad.stdout[-1000:])
        records.append({"case_id":entry["case_id"],"positive_exit_code":ok.returncode,
            "negative_exit_code":bad.returncode,"source_path":str(source.relative_to(REPO)),
            "analysis_sha256":sha(positive / "analysis-report.json"),
            "result_sha256":sha(positive / "result.json"),
            "source_native_sha256":sha(source / "native_samples.jsonl"),
            "video_frames":report["video_frames"],"measurement_keys":sorted(report["measurements"]),
            "synthetic":True,"physical_accepted":False})
        print(suffix, "positive", ok.returncode, "negative", bad.returncode, flush=True)
    summary_name="saved-package-full-summary.json" if args.full_resolution else "saved-package-summary.json"
    (HERE / summary_name).write_text(json.dumps({"format":"c329610-413-2-synthetic-saved-proof-v1",
        "records":records,"selected":False,"original_native_observed":False},indent=2)+"\n")


if __name__ == "__main__":
    main()
