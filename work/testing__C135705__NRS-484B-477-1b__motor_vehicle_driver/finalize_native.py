"""Close four source videos and seal an original alley capture after restoration."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path

from native_capture import FRAMES

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finalize(output: Path, *, case_id: str, restored: bool) -> dict:
    from worker_exchange.native_output import FrameMap, seal_capture
    root = Path(output).resolve()
    source = root / "original-attempt"
    if not restored or not source.is_dir():
        raise ValueError("original alley capture/restoration incomplete")
    inventory = json.loads((source / "inventory.json").read_text())
    if inventory.get("case_id") != case_id or inventory.get("diagnostic_fixture") is not False:
        raise ValueError("original Native alley inventory identity missing")
    frame_map = json.loads((source / "frame_map.json").read_text())["frames"]
    if len(frame_map) != FRAMES:
        raise ValueError("original alley frame map incomplete")
    with FrameMap(root / "video_frames.jsonl") as writer:
        for index, row in enumerate(frame_map):
            if row["video_frame"] != index:
                raise ValueError("original camera frame index differs")
            writer.append(row["frame"], row["time_s"])
    scratch_root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if ".runtime-work" not in scratch_root.parts:
        raise ValueError("camera encoding scratch must live under .runtime-work")
    scratch_root.mkdir(parents=True, exist_ok=True)
    encoders = {}
    with tempfile.TemporaryDirectory(prefix="c135705-camera-", dir=scratch_root) as temporary:
        scratch = Path(temporary)
        for view in VIEWS:
            media = inventory.get("media", {}).get(view)
            if not isinstance(media, dict) or media.get("path") != view + ".zip":
                raise ValueError("original camera source archive missing: " + view)
            archive_path = source / media["path"]
            if sha(archive_path) != media.get("sha256"):
                raise ValueError("original camera source archive changed: " + view)
            images = scratch / view
            images.mkdir()
            with zipfile.ZipFile(archive_path) as archive:
                expected = [f"{i:04d}-{row['frame']}.png" for i, row in enumerate(frame_map)]
                if archive.namelist() != expected:
                    raise ValueError("original camera PNG/frame join differs: " + view)
                for i, name in enumerate(expected):
                    (images / f"{i:06d}.png").write_bytes(archive.read(name))
            target = root / (view + ".mkv")
            if target.exists():
                raise ValueError("refusing to replace original camera video")
            process = subprocess.run(
                ["ffmpeg", "-v", "error", "-xerror", "-framerate", "20",
                 "-i", str(images / "%06d.png"), "-frames:v", str(FRAMES),
                 "-c:v", "ffv1", "-level", "3", str(target)],
                capture_output=True, text=True)
            encoders[view] = process.returncode
            if process.returncode or not target.is_file() or target.stat().st_size == 0:
                raise ValueError("lossless original camera encode failed: " + view + " " + process.stderr[-200:])
    (root / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "native", "diagnostic_fixture": False,
        "source_kind": "original_native",
        "original_inventory_sha256": sha(source / "inventory.json"),
        "physical_acceptance_claimed": False}) + "\n")
    receipt = seal_capture(root, frames=FRAMES,
                           restoration={"restored": True,
                                        "method": "owned sensor/actor cleanup and world settings readback"},
                           errors=[], encoder_exit_codes=encoders,
                           context={"alley_inventory_sha256": sha(source / "inventory.json"),
                                    "free_movement_judgment": "unresolved"})
    return {"case_id": case_id, "capture_seal_sha256": sha(root / "capture-seal.json"),
            "frames": FRAMES, "physical_acceptance_claimed": False,
            "source_digest": receipt["source_digest"]}
