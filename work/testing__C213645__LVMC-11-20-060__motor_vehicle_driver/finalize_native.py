"""Seal four original camera sources and the frame-joined Core episode."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path

from native_acquisition import VIEWS


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finalize(output, *, case_id, restored):
    from worker_exchange.native_output import FrameMap, seal_capture
    root = Path(output).resolve()
    original = root / "original-attempt"
    if not restored or not original.is_dir():
        raise ValueError("original driveway capture/restoration incomplete")
    inventory = json.loads((original / "inventory.json").read_text())
    if inventory.get("case_id") != case_id or inventory.get("diagnostic_fixture") is not False:
        raise ValueError("original Native driveway inventory identity missing")
    frames = json.loads((original / "frame_map.json").read_text())["frames"]
    if len(frames) != 900:
        raise ValueError("original driveway frame map incomplete")
    with FrameMap(root / "video_frames.jsonl") as writer:
        for index, row in enumerate(frames):
            if row["video_frame"] != index:
                raise ValueError("original camera frame index differs")
            writer.append(row["frame"], row["time_s"])
    scratch_root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if ".runtime-work" not in scratch_root.parts:
        raise ValueError("camera encoding scratch must live under .runtime-work")
    scratch_root.mkdir(parents=True, exist_ok=True)
    encoders = {}
    with tempfile.TemporaryDirectory(prefix="c213645-camera-", dir=scratch_root) as temp:
        scratch = Path(temp)
        for name in VIEWS:
            media = inventory.get("media", {}).get(name)
            if not isinstance(media, dict) or media.get("path") != name + ".zip":
                raise ValueError("original camera source archive missing: " + name)
            archive_path = original / media["path"]
            if _sha(archive_path) != media.get("sha256"):
                raise ValueError("original camera source archive changed: " + name)
            images = scratch / name
            images.mkdir()
            with zipfile.ZipFile(archive_path) as archive:
                expected = [f"{i:04d}-{row['frame']}.png" for i, row in enumerate(frames)]
                if archive.namelist() != expected:
                    raise ValueError("original camera PNG/frame join differs: " + name)
                for i, filename in enumerate(expected):
                    (images / f"{i:06d}.png").write_bytes(archive.read(filename))
            target = root / (name + ".mkv")
            if target.exists():
                raise ValueError("refusing to replace original camera video")
            process = subprocess.run(
                ["ffmpeg", "-v", "error", "-xerror", "-framerate", "20",
                 "-i", str(images / "%06d.png"), "-frames:v", "900",
                 "-c:v", "ffv1", "-level", "3", str(target)],
                capture_output=True, text=True)
            encoders[name] = process.returncode
            if process.returncode or not target.is_file() or target.stat().st_size == 0:
                raise ValueError("original camera encode failed: " + name + " " + process.stderr[-200:])
    (root / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "native", "diagnostic_fixture": False,
        "source_kind": "original_native", "original_inventory_sha256": _sha(original / "inventory.json"),
        "physical_acceptance_claimed": False}) + "\n")
    receipt = seal_capture(root, frames=900,
                           restoration={"restored": True,
                                        "method": "owned actor/sensor cleanup and world settings readback"},
                           errors=[], encoder_exit_codes=encoders,
                           context={"driveway_inventory_sha256": _sha(original / "inventory.json"),
                                    "legal_judgment": "unresolved"})
    return {"case_id": case_id, "capture_seal_sha256": _sha(root / "capture-seal.json"),
            "frames": 900, "physical_acceptance_claimed": False,
            "source_digest": receipt["source_digest"]}
