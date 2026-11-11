"""Synthetic 1100-frame saved-source and four-camera software proof."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
OUT = ROOT / ".runtime-work/c125714-saved-full-duration-v1"
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))

from finalizer import CAMERAS, finalize
from worker_exchange.media import audit, check_four_view_sources
from worker_exchange.measurement_contract import validate, verify_report

FRAMES = 1100
CASE = "testing__C125714__NRS-484B-250-1__motor_vehicle_driver__source_verified_precedence"
SIZES = ((1920, 1080), (1280, 720), (1280, 720), (1280, 720))


def body(x):
    return [[x - 1, 4], [x + 1, 4], [x + 1, 6], [x - 1, 6]]


def other_x(i):
    return 14 if i < 200 else 14 - 0.08 * (i - 200)


def ego_x(i):
    return -4 if i < 400 else -4 + 0.08 * (i - 400)


def inside(x):
    return -1 <= x <= 11


def write_sources(attempt):
    attempt.mkdir(parents=True)
    context = {"native_map_id": "synthetic-median-map", "intersection_id": 5,
               "ego_highway_id": 1, "other_highway_id": 2,
               "ego_road_id": 11, "other_road_id": 22,
               "crossing_geometry_source": "synthetic-polygon",
               "all_entrances_source": "synthetic-roadway-inventory",
               "official_device_inventory_source": "synthetic-empty-inventory",
               "median_spacing_source": "synthetic-roadway-pair",
               "same_statutory_crossing": True,
               "official_device_controls_crossing": False,
               "opposite_approach_with_left_turn": False,
               "intersection_polygon_xy_m": [[0, 0], [10, 0], [10, 10], [0, 10]],
               "diagnostic_only": True}
    (attempt / "junction_context.json").write_text(json.dumps(context) + "\n")
    config = {"selected_case_id": CASE, "law_id": "NRS-484B-250-1",
              "cell_id": "C125714", "rate_hz": 20, "duration_s": 55,
              "expected_other_enters_before_ego": True,
              "recording_description": {"channels": []},
              "physical_completion": {"context_sources": ["junction_context.json"],
                                      "body_key": "ego_vertices_m"}}
    (attempt / "config.json").write_text(json.dumps(config) + "\n")
    (attempt / "capture").mkdir()
    entered = False
    with ((attempt / "crossing_history.jsonl").open("x") as history,
          (attempt / "video_frames.jsonl").open("x") as frame_map,
          (attempt / "controller_history.jsonl").open("x") as controls,
          (attempt / "trace.jsonl").open("x") as trace,
          (attempt / "capture/evidence.jsonl").open("x") as evidence):
        for i in range(FRAMES):
            frame, time = 1000 + i, i / 20
            ex, ox = ego_x(i), other_x(i)
            row = {"frame": frame, "time_s": time, "ego_vertices_m": body(ex),
                   "ego": {"intersection_id": 5, "road_id": 11,
                           "body_vertices_xy_m": body(ex)},
                   "other": {"intersection_id": 5, "road_id": 22,
                             "body_vertices_xy_m": body(ox)}}
            history.write(json.dumps(row) + "\n")
            frame_map.write(json.dumps({"video_frame": i, "carla_frame": frame,
                                         "time_s": time}) + "\n")
            other_before_tick = inside(other_x(i - 1)) if i else False
            entered = entered or other_before_tick
            hold = not entered or other_before_tick
            controls.write(json.dumps({"frame": frame, "time_s": time,
                                        "selected_case_id": CASE,
                                        "ego_held": i < 400 or hold,
                                        "other_body_inside_before_tick": other_before_tick,
                                        "other_entered_once_before_tick": entered,
                                        "precedence_hold": hold}) + "\n")
            trace.write(json.dumps({"frame": frame, "time_s": time,
                                    "position_m": [ex, 5, 0],
                                    "speed_mps": 0 if i < 400 else 1.6}) + "\n")
            evidence.write(json.dumps({"original_frame": frame,
                                       "recording_time_s": time,
                                       "diagnostic_only": True}) + "\n")
    for name, (width, height), color in zip(CAMERAS, SIZES,
                                            ("black", "red", "green", "blue")):
        subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                        "-f", "lavfi", "-i", f"color=c={color}:s={width}x{height}:r=20",
                        "-frames:v", str(FRAMES), "-an", "-c:v", "ffv1",
                        "-threads", "1", str(attempt / name)], check=True, timeout=300)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    attempt = OUT / "positive"
    write_sources(attempt)
    check_four_view_sources({name.removesuffix(".mkv"): attempt / name for name in CAMERAS})
    mapping_sha = hashlib.sha256((attempt / "video_frames.jsonl").read_bytes()).hexdigest()
    decodes = {}
    for index, name in enumerate(CAMERAS):
        receipt = audit(attempt / name, FRAMES, mapping_sha256=mapping_sha,
                        receipt=OUT / f"source-decode-{index}.json")
        decodes[name] = {"frames": receipt["frames"],
                         "video_sha256": receipt["video_sha256"]}
    analysis = finalize(attempt, attempt / "analysis-report.json")
    plan = json.loads((PACKAGE / "case-plan.json").read_text())
    contract = json.loads((PACKAGE / "measurement-contract.json").read_text())
    validate(contract, plan["requirement_dispositions"],
             (PACKAGE / "finalizer.py").read_text(), CASE)
    verified = verify_report(contract, analysis, attempt)
    assert analysis["source_report"]["other_enters_before_ego"] is True
    assert analysis["measurements"]["yield_control_attempt"]["value"]["other_entry_seen_before_tick"] is True
    negative = OUT / "missing-controller"
    negative.mkdir()
    for name in ("config.json", "junction_context.json", "crossing_history.jsonl",
                 "video_frames.jsonl", "trace.jsonl", *CAMERAS):
        (negative / name).hardlink_to(attempt / name)
    (negative / "capture").mkdir()
    (negative / "capture/evidence.jsonl").hardlink_to(attempt / "capture/evidence.jsonl")
    try:
        finalize(negative, negative / "analysis-report.json")
    except ValueError as error:
        assert "Missing required source: controller_history.jsonl" in str(error), error
    else:
        raise AssertionError("Missing original controller history was accepted")
    print(json.dumps({"format": "worker-c125714-full-duration-saved-source-proof",
                      "frames": FRAMES, "rate_hz": 20,
                      "source_decodes": decodes,
                      "measurement_keys": sorted(verified),
                      "other_enters_before_ego": True,
                      "negative": "missing_controller_history_rejected",
                      "synthetic_only": True,
                      "physical_acceptance_claimed": False,
                      "legal_conclusion": "unresolved"}))


if __name__ == "__main__":
    main()
