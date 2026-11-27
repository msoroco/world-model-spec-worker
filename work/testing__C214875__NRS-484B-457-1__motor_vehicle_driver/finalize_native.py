"""Close original four-camera curb capture after Native owner cleanup."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

from audit_original_attempt import audit
from native_acquisition import CAMERAS


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _scratch():
    root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if ".runtime-work" not in root.parts:
        raise ValueError("Native scratch must be under .runtime-work")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _encode(source, destination, frames, name, width, height):
    with tempfile.TemporaryDirectory(prefix="c214875-camera-", dir=_scratch()) as temp:
        frame_root = Path(temp)
        with zipfile.ZipFile(source) as archive:
            names = archive.namelist()
            if len(names) != 900:
                raise ValueError("original camera frame count differs: " + name)
            for index, row in enumerate(frames):
                expected = f"{index:04d}-{row['native_frame']}.png"
                if names[index] != expected:
                    raise ValueError("original camera frame identity differs: " + name)
                (frame_root / f"{index:04d}.png").write_bytes(archive.read(expected))
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                        "-framerate", "20", "-i", str(frame_root / "%04d.png"),
                        "-c:v", "ffv1", "-level", "3", "-pix_fmt", "rgb24", str(destination)],
                       check=True, capture_output=True, text=True, timeout=900)
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                            "-show_entries", "stream=width,height,nb_read_frames,r_frame_rate",
                            "-of", "json", str(destination)],
                           check=True, capture_output=True, text=True, timeout=120)
    streams = json.loads(probe.stdout).get("streams", [])
    if len(streams) != 1:
        raise ValueError("original camera encode stream count differs: " + name)
    stream = streams[0]
    if (stream.get("width"), stream.get("height"), stream.get("r_frame_rate"),
            int(stream.get("nb_read_frames", -1))) != (width, height, "20/1", 900):
        raise ValueError("original camera encode differs: " + name)
    return _sha(destination)


def finalize(destination, case_id, operator):
    destination = Path(destination)
    checked = audit(destination, case_id, require_native_attestation=True)
    if checked["frame_count"] != 900:
        raise ValueError("original 900-frame capture incomplete")
    graph = getattr(operator, "pipeline_capture", None)
    if graph is None or not graph.closed or graph.meta.get("extraction_confirmed") is not True:
        raise ValueError("original graph extraction unconfirmed")
    restoration = operator.verify_restoration()
    if not isinstance(restoration, dict) or restoration.get("restored") is not True:
        raise ValueError("Native world restoration readback missing")
    frames = json.loads((destination / "original-attempt/frame-map.json").read_text())["frames"]
    trace = [json.loads(line) for line in (destination / "trace.jsonl").read_text().splitlines()]
    if len(trace) != 900:
        raise ValueError("original graph and curb wheel frame counts differ")
    mapping = []
    for index, (frame, row) in enumerate(zip(frames, trace)):
        if row.get("frame") != frame["native_frame"] or abs(row.get("time_s", -1) - frame["native_time_s"]) > 1e-6:
            raise ValueError("original graph and curb wheel frame join differs")
        mapping.append({"video_frame": index, "carla_frame": frame["native_frame"],
                        "native_frame": frame["native_frame"], "time_s": frame["native_time_s"]})
    (destination / "video_frames.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in mapping))
    config = json.loads((destination / "config.json").read_text())
    sizes = {item["name"]: (item["width"], item["height"]) for item in config["cameras"]}
    if set(sizes) != set(CAMERAS):
        raise ValueError("four original camera definitions differ")
    codes = {}
    for name in CAMERAS:
        _encode(destination / "original-attempt" / (name + ".zip"),
                destination / (name + ".mkv"), frames, name, *sizes[name])
        codes[name] = 0
    if not getattr(operator, "native_attested", False):
        raise ValueError("original operator attestation missing")
    (destination / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "native", "diagnostic_fixture": False,
        "original_wheel_motion_sha256": _sha(destination / "original-attempt/wheel-motion.jsonl"),
        "physical_acceptance_claimed": False}, indent=2, sort_keys=True) + "\n")
    from worker_exchange.native_output import seal_capture
    seal = seal_capture(destination, frames=900, restoration=restoration, errors=[],
                        encoder_exit_codes=codes,
                        context={"case_id": case_id,
                                 "original_wheel_motion_sha256": _sha(destination / "original-attempt/wheel-motion.jsonl")})
    return {"case_id": case_id, "capture_seal_sha256": _sha(destination / "capture-seal.json"),
            "source_digest": seal["source_digest"], "physical_acceptance_claimed": False}
