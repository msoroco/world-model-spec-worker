"""Close four original camera videos after Native restoration and source checks."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path

from driveway_construction import CAMERAS


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finalize(output, case_id):
    from worker_exchange.native_output import FrameMap, seal_capture
    root = Path(output).resolve()
    source = root / "original-attempt"
    receipt_path = source / "capture-receipt.json"
    receipt = json.loads(receipt_path.read_text())
    if (receipt.get("case_id") != case_id or receipt.get("source_kind") != "original_native_capture" or
            receipt.get("diagnostic_fixture") is not False or
            receipt.get("restoration_verified") is not True or
            (source / "capture-incomplete.txt").exists()):
        raise ValueError("original driveway capture or restoration incomplete")
    rows = [json.loads(line) for line in (source / "camera-frame-map.jsonl").read_text().splitlines() if line]
    if len(rows) != 900 or any(row.get("frame") != i or row.get("time_s") != i / 20
                               for i, row in enumerate(rows)):
        raise ValueError("original driveway camera frame map incomplete")
    with FrameMap(root / "video_frames.jsonl") as writer:
        for row in rows:
            writer.append(row["carla_frame"], row["native_time_s"])
    scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if ".runtime-work" not in scratch.parts:
        raise ValueError("camera encoding scratch must live under .runtime-work")
    scratch.mkdir(parents=True, exist_ok=True)
    encoders = {}
    with tempfile.TemporaryDirectory(prefix="lvmc-driveway-camera-", dir=scratch) as temporary:
        temp = Path(temporary)
        for name in CAMERAS:
            archive_path = source / (name + ".zip")
            if sha(archive_path) != receipt.get("camera_source_sha256", {}).get(name):
                raise ValueError("original camera source archive changed: " + name)
            images = temp / name
            images.mkdir()
            with zipfile.ZipFile(archive_path) as archive:
                expected = [f"{i:04d}-{row['carla_frame']}.png" for i, row in enumerate(rows)]
                if archive.namelist() != expected:
                    raise ValueError("original camera PNG/frame join differs: " + name)
                for index, filename in enumerate(expected):
                    (images / f"{index:06d}.png").write_bytes(archive.read(filename))
            target = root / (name + ".mkv")
            if target.exists():
                raise ValueError("refusing to replace original driveway video")
            process = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-framerate", "20",
                                      "-i", str(images / "%06d.png"), "-frames:v", "900",
                                      "-c:v", "ffv1", "-level", "3", str(target)],
                                     capture_output=True, text=True)
            encoders[name] = process.returncode
            if process.returncode or not target.is_file() or target.stat().st_size == 0:
                raise ValueError("lossless original camera encode failed: " + name + " " + process.stderr[-200:])
    (root / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "native", "diagnostic_fixture": False,
        "source_kind": "original_native", "original_receipt_sha256": sha(receipt_path),
        "physical_acceptance_claimed": False}) + "\n")
    sealed = seal_capture(root, frames=900,
                          restoration={"restored": True,
                                       "method": "owned sensors and actors; world settings readback"},
                          errors=[], encoder_exit_codes=encoders,
                          context={"driveway_receipt_sha256": sha(receipt_path),
                                   "frontage_and_exception_judgments": "unresolved"})
    return {"case_id": case_id, "capture_seal_sha256": sha(root / "capture-seal.json"),
            "source_digest": sealed["source_digest"], "physical_acceptance_claimed": False}
