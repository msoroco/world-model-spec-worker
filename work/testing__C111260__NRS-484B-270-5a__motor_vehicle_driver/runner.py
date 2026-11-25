"""Exact, source-gated Native entrypoint for mounted-rider encounters."""

from __future__ import annotations

import argparse
import importlib
import hashlib
import json
import math
import os
import shutil
from pathlib import Path

import native_run
import native_site
from saved_encounter import ASSIGNMENT, CAMERAS, KINDS, RESPONSES


ROOT = Path(__file__).resolve().parent
CASES = {ASSIGNMENT + "__" + kind + "_" + response
         for kind in KINDS for response in RESPONSES}
PROFILE = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def seal_original(attempt, receipt, source_root=ROOT):
    """Seal acquired Native rows after camera encoding and world restoration."""
    from worker_exchange.native_output import seal_capture

    attempt = Path(attempt)
    packet = json.loads((attempt / "encounter-packet.json").read_text(encoding="utf-8"))
    rows = json.loads((attempt / "history.json").read_text(encoding="utf-8"))
    if len(rows) != 900 or receipt.get("frames") != 900:
        raise ValueError("original encounter frame count incomplete")
    for name in ("config.json", "construction.json", "runner.py"):
        shutil.copyfile(Path(source_root) / name, attempt / name)
    with (attempt / "video_frames.jsonl").open("x", encoding="utf-8") as mapping, (
            attempt / "trace.jsonl").open("x", encoding="utf-8") as trace:
        for index, row in enumerate(rows):
            frame = row["frame"]
            time_s = row["time_s"]
            mapping.write(json.dumps({"video_frame": index, "carla_frame": frame,
                                      "native_frame": frame, "time_s": time_s}) + "\n")
            trace.write(json.dumps({"frame": frame, "time_s": time_s,
                                    "position": {"x": row["ego_position_xy_m"][0],
                                                 "y": row["ego_position_xy_m"][1],
                                                 "z": row["ego_position_z_m"]},
                                    "heading_deg": row["ego_heading_deg"],
                                    "speed_mps": row["ego_speed_mps"],
                                    "position_m": row["ego_position_xy_m"],
                                    "rider_position_m": row["rider_position_xy_m"],
                                    "ego_speed_mps": row["ego_speed_mps"],
                                    "rider_speed_mps": row["rider_speed_mps"],
                                    "surface_gap_m": row["surface_gap_m"],
                                    "contact_observed": row["contact_observed"]}) + "\n")
    (attempt / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "native", "diagnostic_fixture": False,
        "case_id": packet["case_id"],
        "site_sha256": packet["native_site"]["sha256"],
        "history_sha256": packet["history"]["sha256"],
        "video_manifest_sha256": _sha(attempt / receipt["video_manifest"]["path"]),
    }, indent=2) + "\n", encoding="utf-8")
    return seal_capture(attempt, frames=900, restoration={"restored": True,
                        "method": receipt["restoration"]}, errors=[],
                        encoder_exit_codes={name: 0 for name, _, _ in PROFILE},
                        context={"case_id": packet["case_id"],
                                 "site_sha256": packet["native_site"]["sha256"],
                                 "original_history_sha256": packet["history"]["sha256"],
                                 "video_manifest_sha256": _sha(attempt / receipt["video_manifest"]["path"])})


def check(root=ROOT):
    config = json.loads((Path(root) / "config.json").read_text(encoding="utf-8"))
    if tuple(config.get(key) for key in ("assignment_id", "law_id", "cell_id", "actor")) != (
            ASSIGNMENT, "NRS-484B-270-5a", "C111260", "motor_vehicle_driver"):
        raise ValueError("wrong exact assignment identity")
    selected = config.get("selected_case_id")
    if selected not in CASES or set(config.get("supported_case_ids", [])) != CASES:
        raise ValueError("exact selected case inventory differs")
    if tuple(config.get(key) for key in ("rate_hz", "duration_s", "frame_count")) != (20, 45, 900):
        raise ValueError("original recording timebase differs")
    if [(camera.get("name"), camera.get("width"), camera.get("height"))
            for camera in config.get("cameras", [])] != list(PROFILE):
        raise ValueError("four source cameras required")
    if (config.get("case", {}).get("case_id") != selected or
            config.get("case", {}).get("rider_kind") != selected[len(ASSIGNMENT) + 2:].rsplit("_", 1)[0] or
            config.get("case", {}).get("motorist_response") != selected.rsplit("_", 1)[1]):
        raise ValueError("selected rider and response differ")
    return selected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args(argv)
    selected = check()
    if args.check:
        return 0
    if args.output_dir is None:
        raise ValueError("new Native output directory required")
    survey_root = os.environ.get("C111260_SITE_ROOT")
    camera_review_path = os.environ.get("C111260_CAMERA_REVIEW")
    camera_review_sha256 = os.environ.get("C111260_CAMERA_REVIEW_SHA256")
    if not survey_root or not camera_review_path or not camera_review_sha256:
        raise ValueError("reviewed site and source-hashed camera plan required")
    site_root = Path(survey_root).resolve()
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    steering_error_divisor = float(config.get("steering_error_divisor", 1.5))
    if not math.isfinite(steering_error_divisor) or not 0.8 <= steering_error_divisor <= 2.0:
        raise ValueError("steering error divisor outside reviewed engineering range")
    site_ref = {"path": "site-survey.json", "sha256": native_site._sha(site_root / "site-survey.json")}
    kind = selected[len(ASSIGNMENT) + 2:].rsplit("_", 1)[0]
    native_site.verify(site_root, site_ref, expected_kind=kind)
    carla = importlib.import_module("carla")
    client = carla.Client(args.host, args.port)
    client.set_timeout(20.0)
    world = client.get_world()
    receipt = native_run.run(world, carla, case_id=selected, site_root=site_root,
                             site_ref=site_ref, camera_review_path=camera_review_path,
                             camera_review_sha256=camera_review_sha256,
                             output_dir=args.output_dir,
                             steering_error_divisor=steering_error_divisor)
    seal_original(args.output_dir, receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
