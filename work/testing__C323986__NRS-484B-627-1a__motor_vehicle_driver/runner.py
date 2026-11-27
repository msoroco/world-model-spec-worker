"""Source-gated Native acquisition for the exact two-way obstruction cases."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from reviewed_scene import ASSIGNMENT, VARIANTS, execute_native, plan


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finish_capture(attempt: Path, scene: dict, adapter: object,
                   original_site: Path) -> None:
    """Seal source bytes only after capture, encoders, and world restoration."""
    if not adapter.restoration_verified or len(adapter.frame_rows) != scene["frames"]:
        raise ValueError("Native capture or restoration incomplete")
    shutil.copy2(original_site, attempt / "original-site.json")
    shutil.copy2(scene["map_path"], attempt / "reviewed-road.xodr")
    with (attempt / "video_frames.jsonl").open("x", encoding="utf-8") as stream:
        for index, row in enumerate(adapter.frame_rows):
            stream.write(json.dumps({"video_frame": index,
                "carla_frame": row["native_frame"], "native_frame": row["native_frame"],
                "time_s": row["time_s"]}, sort_keys=True) + "\n")
    sources = {}
    for view in ("overview", "approach", "reference_corner", "driver_reference"):
        video = attempt / (view + ".mkv")
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-framerate", "20",
                   "-i", str(attempt / "capture" / view / "%06d.png"),
                   "-frames:v", str(scene["frames"]), "-c:v", "libx264", "-preset", "medium",
                   "-pix_fmt", "yuv420p", str(video)]
        subprocess.run(command, check=True, timeout=900)
        sources[view + ".mkv"] = _sha(video)
    from worker_exchange.media import compose_four_views
    compose_four_views({view: attempt / (view + ".mkv") for view in
                       ("overview", "approach", "reference_corner", "driver_reference")},
                       attempt / "video_frames.jsonl", attempt / "raw.mkv")
    for name in ("original-site.json", "reviewed-road.xodr", "road.xodr", "original-motion.json",
                 "original-relation.json", "original-frame-map.json", "trace.jsonl",
                 "video_frames.jsonl", "raw.mkv"):
        sources[name] = _sha(attempt / name)
    for path in sorted((attempt / "capture").rglob("*")):
        if path.is_file():
            sources[str(path.relative_to(attempt))] = _sha(path)
    revision = {"construction_sha256": _sha(attempt / "construction.json"),
                "runner_sha256": _sha(attempt / "runner.py")}
    seal = {"events": ["capture_finished", "encoders_closed", "restoration_verified"],
            "case_id": scene["case_id"], "native_revision": revision,
            "sources": sources, "physical_acceptance_claimed": False}
    (attempt / "capture-seal.json").write_text(json.dumps(seal, indent=2) + "\n")


def check_config(config: dict) -> None:
    case_id = config.get("selected_case_id", "")
    if (case_id not in {ASSIGNMENT + "__" + suffix for suffix in VARIANTS} or
            config.get("law_id") != "NRS-484B-627-1a" or
            config.get("cell_id") != "C323986" or
            config.get("actor") != "motor_vehicle_driver"):
        raise ValueError("exact assignment or case identity mismatch")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 45:
        raise ValueError("20 Hz 45-second capture contract required")
    cameras = config.get("cameras", [])
    if [(c.get("name"), c.get("width"), c.get("height")) for c in cameras] != [
            ("overview", 1920, 1080), ("approach", 1280, 720),
            ("reference_corner", 1280, 720), ("driver_reference", 1280, 720)]:
        raise ValueError("four-view capture profile mismatch")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    config = json.loads(Path("config.json").read_text(encoding="utf-8"))
    check_config(config)
    if args.check:
        print("exact source-gated construction configuration passed")
        return
    if (args.output_dir is None or not args.output_dir.is_dir() or
            args.output_dir.resolve() != Path.cwd().resolve() or
            (args.output_dir / "capture-seal.json").exists()):
        raise ValueError("fresh materialized Native attempt required")
    authority = os.environ.get("C323986_AUTHORITY_ROOT")
    ref_path = os.environ.get("C323986_SITE_REF")
    if not authority or not ref_path:
        raise ValueError("reviewed original highway site source required")
    try:
        site_ref = json.loads(Path(ref_path).read_text(encoding="utf-8"))
        scene = plan(Path(authority), site_ref, config["selected_case_id"])
        from native_adapter import NativeAdapter
        adapter = NativeAdapter(args.host, args.port, args.output_dir)
        adapter.site_road_id = scene["road_id"]
        adapter.assignment_id = ASSIGNMENT
        adapter.case_id = scene["case_id"]
        adapter.trace_id = args.output_dir.name
        try:
            execute_native(scene, adapter)
        finally:
            adapter.close()
        finish_capture(args.output_dir, scene, adapter, Path(authority) / site_ref["path"])
    except Exception as error:
        (args.output_dir / "native-run-status.json").write_text(
            json.dumps({"errors": [str(error)], "case_id": config["selected_case_id"]}, indent=2) + "\n")
        raise


if __name__ == "__main__":
    main()
