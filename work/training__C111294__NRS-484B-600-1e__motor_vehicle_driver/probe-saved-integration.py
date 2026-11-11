"""Synthetic 480-frame C111294 saved/Native-result integration, no CARLA."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE / "native"), str(ROOT / "runtime/pipeline/scenario_pipeline")]
from finalize import finalize_attempt
from worker_exchange.measurement_contract import verify_report
from worker_exchange.native_output import validate_result
from batch_pipeline.carla import validate_attempt


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, allow_nan=False) + "\n" for row in rows))


def make_attempt(destination: Path, suffix: str, full_resolution: bool = False) -> None:
    destination.mkdir()
    (destination / "capture/native").mkdir(parents=True)
    construction = json.loads((HERE / "exact-drafts" / suffix / "primary/construction.json").read_text())
    config = json.loads(next(item["content"] for item in construction["files"]
                             if item["path"] == "config.json"))
    (destination / "config.json").write_text(json.dumps(config) + "\n")
    contract = json.loads(next(item["content"] for item in construction["files"]
                               if item["path"] == "measurement-contract.json"))
    (destination / "measurement-contract.json").write_text(json.dumps(contract) + "\n")
    shutil.copyfile(HERE / "draft-fixtures/road.xodr", destination / "road.xodr")
    (destination / "context.json").write_text(json.dumps({
        "other_vehicle": {"role": "motor_vehicle_driver",
                          "route": "synthetic opposing through lane"},
        "diagnostic_fixture": True,
        "territorial_applicability_verified": False}) + "\n")
    source = HERE / "draft-fixtures" / (suffix + "-synthetic-native-samples.jsonl")
    raw = [json.loads(line) for line in source.read_text().splitlines()]
    native, trace, evidence, mapping, body, capture_frames = [], [], [], [], [], []
    for index, sample in enumerate(raw):
        frame, time_s = index + 100, (index + 1) / 20
        x, y, z = sample["ego_position_m"]
        speed = math.sqrt(sum(v*v for v in sample["ego_velocity_mps"]))
        vertices = [[x + dx, y + dy, z + h] for dx in (-2.0, 2.0)
                    for dy in (-1.0, 1.0) for h in (0, 1.5)]
        sample.update(native_frame=frame, time_s=time_s,
                      ego_body_vertices_m=vertices,
                      other_body_vertices_m=[[sample["other_position_m"][0] + dx,
                          sample["other_position_m"][1] + dy, 0]
                          for dx in (-2.0, 2.0) for dy in (-1.0, 1.0)])
        native.append(sample)
        trace.append({"frame": frame, "time_s": time_s,
            "position": {"x": x, "y": y, "z": z}, "position_m": [x, y, z],
            "heading_deg": 90.0, "speed_mps": speed, "speed_mph": speed / .44704,
            "control": {"throttle": .5, "brake": 0, "hand_brake": False},
            "synthetic_diagnostic": True,
            "speed_provenance": "synthetic_native_sample"})
        evidence.append({"original_frame": frame, "replay_frame": frame,
            "actor_id": sample["ego_actor_id"], "recording_time_s": time_s,
            "replay_simulation_time_s": time_s,
            "ego": {"position_m": [x, y, z], "heading_deg": 90.0,
                    "speed_mps": speed,
                    "speed_provenance": "synthetic_native_sample",
                    "body_vertices_m": vertices},
            "world": {"weather": {"cloudiness": 0, "precipitation": 0,
                                  "wetness": 0, "fog_density": 0},
                      "road_projection": {"road_id": 1, "section_id": 0,
                                          "lane_id": -1, "s_m": index * speed / 20}}})
        mapping.append({"video_frame": index, "native_frame": frame,
                        "carla_frame": frame, "time_s": time_s})
        body.append({"frame": frame, "time_s": time_s, "body_vertices_m": vertices})
        capture_frames.append({"frame": frame, "time_s": time_s,
            "simulation_time": time_s,
            "base": f"graphs/base/{frame:08d}.pkl",
            "abstract": f"graphs/abstract/{frame:08d}.pkl",
            "synthetic_diagnostic": True})
    for name, rows in (("native_samples.jsonl", native), ("trace.jsonl", trace),
                       ("capture/evidence.jsonl", evidence),
                       ("video_frames.jsonl", mapping),
                       ("body_history.jsonl", body),
                       ("capture/native/frames.jsonl", capture_frames)):
        write_rows(destination / name, rows)
    (destination / "capture/recorder_info.txt").write_text(
        "Create 101: vehicle.tesla.model3\nCreate 202: vehicle.tesla.model3\n")
    (destination / "capture/manifest.json").write_text(json.dumps({
        "extraction_confirmed": True, "frames": 480,
        "required_observations": [], "sources": {
            "road.xodr": sha(destination / "road.xodr"),
            "trace.jsonl": sha(destination / "trace.jsonl")},
        "synthetic_diagnostic": True}) + "\n")
    for camera in config["cameras"]:
        size = f'{camera["width"]}x{camera["height"]}' if full_resolution else "32x32"
        subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", f"color=c=black:s={size}:r=20:d=24",
            "-frames:v", "480", "-c:v", "ffv1",
            str(destination / (camera["name"] + ".mkv"))], check=True, timeout=120)


def main() -> None:
    scratch = Path(tempfile.mkdtemp(dir=ROOT / ".runtime-work",
                                    prefix="c111294-saved-probe-"))
    results = []
    for suffix in ("below_80_mph", "inside_80_mph", "at_80_mph", "above_80_mph"):
        attempt = scratch / suffix
        make_attempt(attempt, suffix)
        source_hashes = {str(p.relative_to(attempt)): sha(p) for p in attempt.rglob("*") if p.is_file()}
        report = finalize_attempt(attempt, attempt / "analysis-report.json")
        result = json.loads((attempt / "result.json").read_text())
        validate_result(result)
        if source_hashes != {str(p.relative_to(attempt)): sha(p) for p in attempt.rglob("*")
                             if p.is_file() and p.name not in ("analysis-report.json", "result.json")
                             and "channels" not in p.parts}:
            raise ValueError("Saved analysis changed original source")
        contract = json.loads((attempt / "measurement-contract.json").read_text())
        verify_report(contract, report, attempt)
        construction = json.loads((HERE / "exact-drafts" / suffix / "primary/construction.json").read_text())
        checked = validate_attempt(attempt, {"case": {"case_id": result["case_id"],
            "recording_description": result["recording_description"], "sweep_measurements": []},
            "cell": {"cell_id": "C111294"}, "actor": "motor_vehicle_driver"},
            construction, {"recorded_exit_code": 0}, {})
        if not checked["rebuild_required"] or result["accepted"] or not report["diagnostic_fixture"]:
            raise ValueError("Synthetic diagnostic falsely claimed physical acceptance")
        missing = scratch / (suffix + "-missing-source")
        changed = scratch / (suffix + "-changed-frame")
        for diagnostic in (missing, changed):
            shutil.copytree(attempt, diagnostic,
                            ignore=shutil.ignore_patterns("analysis-report.json", "result.json", "channels"))
        (missing / "native_samples.jsonl").unlink()
        frame_rows = [json.loads(line) for line in
                      (changed / "capture/evidence.jsonl").read_text().splitlines()]
        frame_rows[200]["original_frame"] += 1
        write_rows(changed / "capture/evidence.jsonl", frame_rows)
        negatives = []
        for diagnostic, expected_error in (
                (missing, "Missing required source: native_samples.jsonl"),
                (changed, "Original Native/Core frame identity differs")):
            try:
                finalize_attempt(diagnostic, diagnostic / "analysis-report.json")
            except ValueError as error:
                if expected_error not in str(error):
                    raise
                negatives.append(expected_error)
            else:
                raise ValueError("Synthetic negative was accepted: " + diagnostic.name)
        results.append({"case_suffix": suffix, "relation": report["measurements"]["speed_relation"]["value"]["measured_relation"],
            "frames": report["original_joins"]["frames"], "video_frames": report["video_frames"],
            "source_preserved": True, "validator_passed": True,
            "analysis_sha256": sha(attempt / "analysis-report.json"),
            "result_sha256": sha(attempt / "result.json"),
            "diagnostic_fixture": True, "negative_errors": negatives,
            "ready": False})
    summary = {"format": "c111294-synthetic-saved-integration-v1",
               "results": results, "scope": "CPU synthetic saved Native/Core/video validation only",
               "carla_executed": False, "accepted": False, "ready": False}
    (HERE / "synthetic-saved-integration.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__": main()
