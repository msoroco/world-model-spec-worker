"""Original source-gated rider capture for a reviewed adjacent path site.

The Native adapter is supplied and hash-bound at local execution. This module
owns the exact 20 Hz route, body, camera and cleanup contract; it does not
provide a substitute municipal source or claim physical path usability.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil

from path_observation import ASSIGNMENT, DEVICES
from path_route import _inside, _polygon
from source_site import REQUIRED, load_reviewed_site, sha


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
FRAMES = 900


def _case_parts(case_id: str) -> tuple[str, str, str]:
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("exact rider case identity required")
    parts = case_id.removeprefix(ASSIGNMENT + "__").split("__")
    if (len(parts) != 3 or parts[0] not in DEVICES or
            parts[1] not in ("path", "roadway") or
            parts[2] not in ("usable_path", "unusable_path")):
        raise ValueError("exact rider case variables required")
    return parts[0], parts[1], parts[2].removesuffix("_path")


def check(root: str | Path | None = None) -> tuple[str, str, str, str]:
    root = Path(root or Path(__file__).resolve().parent)
    config = json.loads((root / "config.json").read_text())
    case_id = config.get("selected_case_id")
    device, target, condition = _case_parts(case_id)
    if (config.get("assignment_id") != ASSIGNMENT or
            config.get("law_id") != "LVMC-11-40-120" or
            config.get("cell_id") != "C233829" or
            config.get("actor") != "cycle_or_scooter_operator" or
            config.get("rate_hz") != 20 or config.get("duration_s") != 45):
        raise ValueError("rider construction identity or capture clock changed")
    names = [c if isinstance(c, str) else c.get("name") for c in config.get("cameras", [])]
    if names != list(CAMERAS):
        raise ValueError("four camera profile changed")
    return case_id, device, target, condition


def _sample(adapter, actor, site: dict, frame: int, index: int, first_time: float) -> dict:
    sample = adapter.sample_rider(actor)
    if (sample.get("native_frame") != frame or
            sample.get("ego_device_type") != site["ego_device_type"] or
            not sample.get("ego_actor_id")):
        raise ValueError("original rider identity or Native frame mismatch")
    corners = sample.get("body_corners_xy")
    if not isinstance(corners, list) or len(corners) < 4:
        raise ValueError("original rider body corners required")
    path = _polygon(site["path_polygon"])
    roadway = _polygon(site["roadway_polygon"])
    for corner in corners:
        if not isinstance(corner, list) or len(corner) != 2:
            raise ValueError("original rider body corner malformed")
    return {"frame_index": index, "native_frame": frame,
            "time_s": round(index / 20, 6),
            "ego_actor_id": sample["ego_actor_id"],
            "ego_device_type": sample["ego_device_type"],
            "ego_body_on_roadway": any(_inside(tuple(c), roadway) for c in corners),
            "ego_body_on_designated_path": any(_inside(tuple(c), path) for c in corners),
            "body_corners_xy": corners,
            "first_native_elapsed_s": first_time}


def capture_original(adapter, manifest_path, site_path, adapter_module_path,
                     output_dir, root=None, pipeline_factory=None):
    root = Path(root or Path(__file__).resolve().parent)
    case_id, device, target, condition = check(root)
    reviewed = load_reviewed_site(manifest_path, site_path, case_id,
                                  device, target, condition)
    manifest_path, site_path = Path(manifest_path), Path(site_path)
    manifest = json.loads(manifest_path.read_text())
    adapter_module_path = Path(adapter_module_path)
    if (not adapter_module_path.is_file() or adapter_module_path.is_symlink() or
            sha(adapter_module_path) != manifest.get("native_adapter_sha256") or
            not callable(getattr(adapter, "provenance", None)) or
            adapter.provenance() != "original_native"):
        raise ValueError("hash-bound original Native adapter required")
    output = Path(output_dir)
    if (not output.is_dir() or
            not all((output / p).is_file() for p in
                    ("construction.json", "config.json", "runner.py"))):
        raise ValueError("materialized exact Native attempt required")
    if any((output / p).exists() for p in
           ("rider-history.jsonl", "camera-frame-map.jsonl", "capture-seal.json")):
        raise ValueError("refusing to overwrite original rider capture")
    source_dir = output / "reviewed-site"
    if source_dir.exists():
        raise ValueError("reviewed source already materialized")
    source_dir.mkdir()
    shutil.copy2(manifest_path, source_dir / "source-manifest.json")
    shutil.copy2(site_path, source_dir / "site-context.json")
    for name in REQUIRED:
        relative = Path(manifest["sources"][name]["path"])
        destination = source_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(manifest_path.parent / relative, destination)
    shutil.copy2(adapter_module_path, source_dir / "native-adapter.py")
    actor = pipeline = None
    cameras_started = cameras_finished = False
    restored = False
    rows, camera_rows = [], []
    try:
        route = reviewed["route"]["route_waypoints"]
        actor = adapter.spawn_rider(device, route[0])
        if pipeline_factory is None:
            from pipeline_capture import PipelineCapture
            pipeline_factory = PipelineCapture
        config = json.loads((root / "config.json").read_text())
        pipeline = pipeline_factory(adapter.pipeline_client(), actor, output,
                                    case_id, required_observations=tuple(config.get("required_atoms", [])))
        adapter.start_cameras(output, CAMERAS)
        cameras_started = True
        first_frame = first_time = None
        for index in range(FRAMES):
            adapter.set_rider_target(actor, route, index, FRAMES)
            adapter.tick_world()
            snapshot = adapter.world().get_snapshot()
            frame = snapshot.frame
            elapsed = snapshot.timestamp.elapsed_seconds
            if index == 0:
                first_frame, first_time = frame, elapsed
            if frame != first_frame + index:
                raise ValueError("original Native frame gap")
            row = _sample(adapter, actor, reviewed["site"], frame, index, first_time)
            camera_frames = adapter.camera_frame_ids(frame)
            if camera_frames != {name: frame for name in CAMERAS}:
                raise ValueError("four cameras not joined to original Native frame")
            captured = pipeline.capture(frame, elapsed)
            if captured.get("frame") != frame or captured.get("time_s") != elapsed:
                raise ValueError("PipelineCapture frame join mismatch")
            rows.append(row)
            camera_rows.append({"frame_index": index, "native_frame": frame,
                                "time_s": row["time_s"], "camera_frames": camera_frames})
        videos = adapter.finish_cameras()
        cameras_finished = True
        if not isinstance(videos, dict) or set(videos) != set(CAMERAS):
            raise ValueError("four original camera outputs required")
        for name in CAMERAS:
            path = output / (name + ".mkv")
            if Path(videos[name]).resolve() != path.resolve() or not path.is_file() or not path.stat().st_size:
                raise ValueError("original camera output missing: " + name)
        pipeline.close(confirmed=True)
        native_sources = adapter.finish_native_capture(output, rows)
        if not isinstance(native_sources, list):
            raise ValueError("original Native source list required")
        for name in native_sources:
            relative = Path(name)
            path = output / relative
            if relative.is_absolute() or ".." in relative.parts or not path.is_file() or not path.stat().st_size:
                raise ValueError("original Native source missing: " + str(name))
        (output / "rider-history.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
        (output / "camera-frame-map.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in camera_rows))
        (output / "video_frames.jsonl").write_text("".join(json.dumps({"video_frame": i,
            "carla_frame": row["native_frame"], "native_frame": row["native_frame"],
            "time_s": row["time_s"]}, sort_keys=True) + "\n" for i, row in enumerate(camera_rows)))
    finally:
        try:
            if pipeline is not None and not pipeline.closed:
                pipeline.close(confirmed=False)
        finally:
            try:
                if cameras_started and not cameras_finished:
                    adapter.abort_cameras()
            finally:
                try:
                    if actor is not None:
                        actor.destroy()
                finally:
                    restored = adapter.restore_world() is True
    if not restored:
        raise ValueError("original world restoration readback missing")
    files = ["rider-history.jsonl", "camera-frame-map.jsonl", "video_frames.jsonl",
             "reviewed-site/source-manifest.json", "reviewed-site/site-context.json",
             "reviewed-site/native-adapter.py", *[name + ".mkv" for name in CAMERAS],
             *native_sources, *["reviewed-site/" + manifest["sources"][name]["path"] for name in REQUIRED]]
    seal = {"format": "adjacent-path-original-native-seal-v1", "case_id": case_id,
            "provenance_kind": "native", "diagnostic_fixture": False,
            "frames": FRAMES, "capture_rate_hz": 20,
            "reviewed_manifest_sha256": sha(manifest_path), "reviewed_site_sha256": sha(site_path),
            "restoration": {"restored": True},
            "native_revision": {name: sha(output / name) for name in
                                ("construction.json", "config.json", "runner.py")},
            "sources": {name: sha(output / name) for name in files}}
    (output / "capture-seal.json").write_text(json.dumps(seal, sort_keys=True, indent=2) + "\n")
    return {"case_id": case_id, "frames": FRAMES, "capture_seal_sha256": sha(output / "capture-seal.json"),
            "physical_path_usability_verified": False, "legal_judgment": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--reviewed-manifest", default=os.environ.get("C233829_REVIEWED_MANIFEST"))
    parser.add_argument("--reviewed-site", default=os.environ.get("C233829_REVIEWED_SITE"))
    parser.add_argument("--adapter-module", default=os.environ.get("C233829_NATIVE_ADAPTER_MODULE"))
    parser.add_argument("--output-dir")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    case_id, device, target, condition = check()
    if args.check:
        print("adjacent-path exact case preflight passed: " + case_id)
        return
    if not all((args.reviewed_manifest, args.reviewed_site, args.adapter_module,
                args.output_dir, args.host, args.port)):
        raise ValueError("reviewed original source, adapter and Native endpoint required")
    load_reviewed_site(args.reviewed_manifest, args.reviewed_site, case_id, device, target, condition)
    manifest = json.loads(Path(args.reviewed_manifest).read_text())
    if sha(Path(args.adapter_module)) != manifest.get("native_adapter_sha256"):
        raise ValueError("reviewed Native adapter hash mismatch")
    spec = importlib.util.spec_from_file_location("adjacent_path_native_adapter", args.adapter_module)
    if spec is None or spec.loader is None:
        raise ValueError("original Native adapter module missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    adapter = module.open_native_adapter(args.host, args.port)
    try:
        print(capture_original(adapter, args.reviewed_manifest, args.reviewed_site,
                               args.adapter_module, args.output_dir))
    finally:
        adapter.close()


if __name__ == "__main__":
    main()
