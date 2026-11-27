"""Run the recorded-only finalizer on explicit synthetic sources and a damaged copy."""
import hashlib
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
if not os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT") or not Path(
        os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve().is_relative_to(
            (REPO / ".runtime-work").resolve()):
    raise RuntimeError("Export a runtime output root under .runtime-work before runtime imports")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
sys.path.insert(0, str(REPO / "runtime/python"))

from finalize import finalize
from geometry import open_drive
from worker_exchange.measurement_contract import validate as validate_measurements
from worker_exchange.measurement_contract import verify_report


def rows(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(value, allow_nan=False) + "\n" for value in values))


def build(attempt, suffix):
    attempt.mkdir()
    if suffix == "a":
        config = json.loads((ROOT / "config.json").read_text())
    else:
        bundle = json.loads((ROOT / "cases/condition_b/construction.json").read_text())
        config = json.loads(next(item["content"] for item in bundle["files"]
                                 if item["path"] == "config.json"))
    (attempt / "config.json").write_text(json.dumps(config) + "\n")
    road = [-100.0, -3.5, 100.0, 3.5]
    obstruction = [0.0, 1.0, 5.0, 3.4]
    ego = [.1, -3.4, 4.9, .5 if suffix == "a" else -1.2]
    flags = {name: False for name in ("traffic_conflict", "law_direction",
                                       "police_direction", "traffic_device")}
    reviewed = {name + "_reviewed": True for name in flags}
    samples, mappings, cameras, traces, evidence, native_frames = [], [], [], [], [], []
    for index in range(600):
        frame = index + 370
        time = index / 20
        traffic_x = -10 if suffix == "a" else -80 + index * 3 / 20
        traffic_speed = 0 if suffix == "a" else 3
        samples.append({"native_frame": frame, "time_s": time, "source_kind": "synthetic_cpu",
                        "road_xy_m": road, "obstruction_xy_m": obstruction,
                        "obstruction_kind": "physical_obstruction", "ego_body_xy_m": ego,
                        "ego_speed_m_s": 0, "passing_body_xy_m": [traffic_x, -.8, traffic_x + 4, .8],
                        "passing_speed_m_s": traffic_speed, "exceptions": flags,
                        "exception_source": reviewed, "controller_clearance_m": .5})
        mappings.append({"video_frame": index, "carla_frame": frame,
                         "native_frame": frame, "time_s": time,
                         "camera_native_frames": {view: frame for view in
                                                  ("overview", "approach", "reference_corner", "driver_reference")}})
        cameras.extend({"frame": index, "native_frame": frame, "camera": view,
                        "source_kind": "synthetic_cpu", "rgb_sha256": "a" * 64}
                       for view in ("overview", "approach", "reference_corner", "driver_reference"))
        center_y = (ego[1] + ego[3]) / 2
        traces.append({"frame": frame, "position_m": [2.5, center_y, 1.1], "speed_mps": 0})
        evidence.append({"original_frame": frame, "ego": {
            "position_m": [2.5, center_y, 1.1], "speed_mps": 0}})
        native_frames.append({"native_frame": frame, "time_s": time})
    rows(attempt / "native_samples.jsonl", samples)
    rows(attempt / "video_frames.jsonl", mappings)
    rows(attempt / "camera-frames.jsonl", cameras)
    rows(attempt / "trace.jsonl", traces)
    rows(attempt / "capture/evidence.jsonl", evidence)
    rows(attempt / "capture/native/frames.jsonl", native_frames)
    (attempt / "exception-context.json").write_text(json.dumps({
        "case_id": config["case_id"], "source_kind": "synthetic_cpu",
        "exceptions": flags, "exception_source": reviewed}) + "\n")
    (attempt / "obstruction-inventory.json").write_text(json.dumps({
        "source_kind": "synthetic_cpu", "obstruction_kind": "physical_obstruction",
        "obstruction_xy_m": obstruction, "physical_cause_confirmed": False}) + "\n")
    (attempt / "road.xodr").write_text(open_drive())
    for index, view in enumerate(("overview", "approach", "reference_corner", "driver_reference")):
        call = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                               "-f", "lavfi", "-i", "color=c=" + ("red", "blue", "green", "yellow")[index] + ":s=64x36:r=20",
                               "-frames:v", "600", "-c:v", "ffv1", str(attempt / (view + ".mkv"))],
                              capture_output=True, text=True, timeout=120)
        if call.returncode:
            raise RuntimeError("Synthetic fixture video failed: " + call.stderr[-300:])


def main(suffix):
    with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work", prefix="c135702-finalizer-") as temp:
        folder = Path(temp)
        attempt = folder / "attempt"
        build(attempt, suffix)
        damaged = folder / "damaged"
        shutil.copytree(attempt, damaged)
        (damaged / "camera-frames.jsonl").unlink()
        try:
            finalize(damaged, folder / "rejected-analysis.json")
        except ValueError as error:
            if "Missing required source: camera-frames.jsonl" not in str(error):
                raise
        else:
            raise AssertionError("Missing original camera source was accepted")
        inventory_missing = folder / "inventory-missing"
        shutil.copytree(attempt, inventory_missing)
        (inventory_missing / "obstruction-inventory.json").unlink()
        try:
            finalize(inventory_missing, folder / "inventory-rejected-analysis.json")
        except ValueError as error:
            if "Missing required source: obstruction-inventory.json" not in str(error):
                raise
        else:
            raise AssertionError("Missing case-specific obstruction inventory was accepted")
        report = finalize(attempt, folder / "analysis.json")
        plan = json.loads((ROOT / "case-plan.json").read_text())
        contract = json.loads((ROOT / ("measurement-condition_" + suffix + ".json")).read_text())
        selected = validate_measurements(contract, plan["requirement_dispositions"],
                                         (ROOT / "finalize.py").read_text(),
                                         report["case_id"])
        verified = verify_report(contract, report, attempt)
        assert len(selected) == len(verified) == 3
        result = json.loads((attempt / "result.json").read_text())
        assert report["analysis_complete"] and report["source_video_frames"] == {
            name: 600 for name in ("overview", "approach", "reference_corner", "driver_reference")}
        assert result["diagnostic_fixture"] and not result["setup_confirmed"]
        assert not result["maneuver_completed"] and not result["legal_verdict_claimed"]
        assert len(result["recording_evidence"]) == 9
        print(json.dumps({"format": "c135702-synthetic-finalizer-proof-v1",
                          "case_id": result["case_id"], "frames": report["source_join"]["frames"],
                          "camera_frames": report["source_join"]["camera_frames"],
                          "channel_count": len(result["recording_evidence"]),
                          "missing_camera_rejected": True,
                          "missing_inventory_rejected": True,
                          "selected_measurements_verified": len(verified),
                          "analysis_sha256": hashlib.sha256((folder / "analysis.json").read_bytes()).hexdigest(),
                          "original_native_observed": False,
                          "legal_verdict_claimed": False}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-suffix", choices=("a", "b"), required=True)
    main(parser.parse_args().case_suffix)
