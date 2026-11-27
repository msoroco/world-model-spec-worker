"""Capture source-grounded original bridge motion and four camera streams."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from bridge_native import CAMERAS, construct, destroy_owned, require_adapter
from bridge_observations import measure_crossing, verify_site_bundle


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, text):
    path = Path(path)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(text)


def acquire(adapter, site_path: Path, site_sha256: str, case: dict, output: Path,
            *, spawn_adjust_m: float = 0.0) -> dict:
    """Own world settings, actors, capture and closure for one fresh attempt."""
    output = Path(output)
    if not output.is_dir() or not (output / "construction.json").is_file():
        raise ValueError("materialized fresh exact-case attempt required")
    if any((output / name).exists() for name in ("original-motion.jsonl", "bridge-site.json")):
        raise ValueError("original capture already exists; retain attempt")
    require_adapter(adapter)
    site = verify_site_bundle(site_path, site_sha256, case["case_id"])
    original_settings = adapter.snapshot_settings()
    owned = []
    rows = []
    mapping = []
    files = {name: [] for name in CAMERAS}
    errors = []
    destroyed = []
    try:
        adapter.configure_sync(rate_hz=20)
        if adapter.readback_sync(rate_hz=20) is not True:
            raise ValueError("original 20 Hz world readback failed")
        built = construct(adapter, site, case, owned, spawn_adjust_m=spawn_adjust_m)
        for index in range(900):
            tick, images = adapter.tick_capture(index, built["ego"], built["cameras"])
            if not isinstance(tick, dict) or not isinstance(images, dict) or set(images) != set(CAMERAS):
                raise ValueError("original tick or four camera frames missing")
            row = dict(tick)
            row["index"] = index
            if row.get("original_frame") is None or row.get("time_s") is None:
                raise ValueError("original simulator frame/time missing")
            rows.append(row)
            mapping.append({"video_frame": index, "carla_frame": row["original_frame"],
                            "native_frame": row["original_frame"], "time_s": row["time_s"]})
            for name in CAMERAS:
                pixels = images[name]
                if not isinstance(pixels, bytes) or not pixels.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("original PNG source missing: " + name)
                path = output / f"{name}-{index:06d}.png"
                with path.open("xb") as stream:
                    stream.write(pixels)
                files[name].append({"frame": row["original_frame"],
                                    "path": path.name, "sha256": sha(path)})
        measurement = measure_crossing(site, rows, case["case_id"])
    except Exception as error:
        errors.append(str(error))
        raise
    finally:
        destroyed = destroy_owned(adapter, owned, original_settings)
        if errors:
            _write(output / "native-run-status.json", json.dumps(
                {"case_id": case["case_id"], "errors": errors,
                 "destroyed_actor_ids": destroyed, "world_restored": True},
                sort_keys=True, indent=2) + "\n")
    source_root = Path(site_path).resolve().parent
    shutil.copy2(site_path, output / "bridge-site.json")
    source_refs = [site["maximum_declaration_source"], site["stationing_source"]]
    source_refs.extend(site["authority"].values())
    for sign in site["signs"].values():
        source_refs.extend((sign["erected_source"], sign["maintained_source"]))
    for ref in source_refs:
        destination = output / ref["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copy2(source_root / ref["path"], destination)
    _write(output / "original-motion.jsonl", "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    _write(output / "video_frames.jsonl", "".join(json.dumps(row, sort_keys=True) + "\n" for row in mapping))
    _write(output / "camera-source-manifest.json", json.dumps(
        {"case_id": case["case_id"], "cameras": files}, sort_keys=True, indent=2) + "\n")
    _write(output / "original-source-receipt.json", json.dumps(
        {"case_id": case["case_id"], "site_sha256": sha(output / "bridge-site.json"),
         "trace_sha256": sha(output / "original-motion.jsonl"),
         "frame_map_sha256": sha(output / "video_frames.jsonl"),
         "camera_manifest_sha256": sha(output / "camera-source-manifest.json"),
         "source_frame_count": 900, "world_restored": True,
         "destroyed_actor_ids": destroyed, "measurement": measurement,
         "physical_acceptance_claimed": False, "legal_verdict_claimed": False},
        sort_keys=True, indent=2) + "\n")
    for name in CAMERAS:
        command = ["ffmpeg", "-v", "error", "-nostdin", "-y", "-framerate", "20",
                   "-start_number", "0", "-i", f"{name}-%06d.png", "-c:v", "ffv1", f"{name}.mkv"]
        subprocess.run(command, cwd=output, check=True, timeout=1800)
    return {"case_id": case["case_id"], "original_frame_count": 900,
            "world_restored": True, "measurement": measurement,
            "video_sources": {name: sha(output / f"{name}.mkv") for name in CAMERAS}}
