"""Full 55-second synthetic source and saved-finalizer CPU proof.

Generated media stays under .runtime-work. This is diagnostic software evidence,
not a Native recording, official-device review, or legal timing judgment.
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
OUT = ROOT / ".runtime-work/c125714-250-2-saved-full-duration-v1"
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
from camera_setup import SIZES
from finalizer import CAMERAS, finalize
from worker_exchange.media import check_four_view_sources

FRAMES = 1100
CASE = "testing__C125714__NRS-484B-250-2__motor_vehicle_driver__source_verified_other_right_near_time"


def body(x, y):
    return [[x-.3,y-.3],[x+.3,y-.3],[x+.3,y+.3],[x-.3,y+.3]]


def ego_x(index):
    return -8 if index < 280 else min(9, -8 + .1 * (index - 280))


def other_y(index):
    return -8 if index < 250 else min(9, -8 + .1 * (index - 250))


def write_sources(attempt):
    attempt.mkdir(parents=True)
    context = {"intersection_polygon_xy_m": [[-5,-5],[5,-5],[5,5],[-5,5]],
               "intersection_id": 7, "ego_highway_id": 1, "other_highway_id": 2,
               "device_inventory_source": "synthetic device inventory; no physical claim",
               "approach_geometry_source": "synthetic orthogonal approach fixture",
               "ego_approach_heading_deg": 0, "other_approach_heading_deg": 90,
               "ego_approach_origin_xy_m": [-8,0],
               "other_approach_origin_xy_m": [0,-8]}
    (attempt / "road_geometry.json").write_text(json.dumps(context) + "\n")
    cfg = {"selected_case_id": CASE, "law_id": "NRS-484B-250-2",
           "cell_id": "C125714", "rate_hz": 20, "duration_s": 55,
           "recording_description": {"diagnostic_only": True},
           "physical_completion": {"context_sources": ["road_geometry.json"],
                                   "body_key": "ego_vertices_m"}}
    (attempt / "config.json").write_text(json.dumps(cfg) + "\n")
    (attempt / "capture").mkdir()
    with ((attempt / "crossing_history.jsonl").open("x") as history,
          (attempt / "video_frames.jsonl").open("x") as mapping,
          (attempt / "trace.jsonl").open("x") as trace,
          (attempt / "capture/evidence.jsonl").open("x") as evidence):
        for index in range(FRAMES):
            frame, time_s = 1000 + index, index / 20
            ex, oy = ego_x(index), other_y(index)
            history.write(json.dumps({"frame": frame, "time_s": time_s,
                "ego_vertices_m": body(ex,0),
                "ego": {"position_xy_m": [ex,0], "body_vertices_xy_m": body(ex,0)},
                "other": {"position_xy_m": [0,oy], "body_vertices_xy_m": body(0,oy)}}) + "\n")
            mapping.write(json.dumps({"video_frame": index, "carla_frame": frame,
                                      "time_s": time_s}) + "\n")
            trace.write(json.dumps({"frame": frame, "time_s": time_s,
                                    "position_m": [ex,0,0]}) + "\n")
            evidence.write(json.dumps({"original_frame": frame,
                                       "recording_time_s": time_s,
                                       "diagnostic_only": True}) + "\n")
    for name, (width, height) in SIZES.items():
        subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                        "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r=20",
                        "-frames:v", str(FRAMES), "-an", "-c:v", "ffv1", "-threads", "1",
                        str(attempt / (name + ".mkv"))], check=True, timeout=300)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    attempt = OUT / "positive"
    write_sources(attempt)
    decoded = check_four_view_sources({name.removesuffix(".mkv"): attempt / name
                                      for name in CAMERAS})
    report = finalize(attempt, attempt / "analysis-report.json")
    assert report["other_is_to_ego_right"] is True
    assert report["first_body_entry"]["other"]["frame"] < report["first_body_entry"]["ego"]["frame"]
    assert "unresolved" in report["approximately_same_time_judgment"]
    negative = OUT / "missing-geometry"
    negative.mkdir()
    (negative / "capture").mkdir()
    for name in ("config.json", "crossing_history.jsonl", "video_frames.jsonl",
                 "trace.jsonl", *CAMERAS):
        (negative / name).hardlink_to(attempt / name)
    (negative / "capture/evidence.jsonl").hardlink_to(attempt / "capture/evidence.jsonl")
    try:
        finalize(negative, negative / "analysis-report.json")
    except ValueError as error:
        assert "Missing required source: road_geometry.json" in str(error), error
    else:
        raise AssertionError("Missing original road geometry was accepted")
    print(json.dumps({"format": "worker-c125714-250-2-full-duration-saved-proof",
                      "frames": FRAMES, "rate_hz": 20,
                      "source_decodes": decoded,
                      "first_body_entry": report["first_body_entry"],
                      "entry_delta_s": report["ego_minus_other_entry_time_s"],
                      "negative": "missing_source_geometry_rejected",
                      "synthetic_only": True, "physical_acceptance_claimed": False,
                      "legal_judgment": "unresolved"}, allow_nan=False))


if __name__ == "__main__":
    main()
