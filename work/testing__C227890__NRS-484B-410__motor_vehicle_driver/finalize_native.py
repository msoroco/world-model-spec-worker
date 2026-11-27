"""Close a source-reviewed original parked departure for saved-only processing."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

from audit_original_attempt import audit

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _scratch():
    root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if ".runtime-work" not in root.parts:
        raise ValueError("Native scratch must be under .runtime-work")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _encode_view(source, destination, name, frames, width, height):
    with tempfile.TemporaryDirectory(prefix="c227890-encode-", dir=_scratch()) as temp:
        png_root = Path(temp)
        with zipfile.ZipFile(source) as archive:
            names = archive.namelist()
            if len(names) != 900:
                raise ValueError("original camera frame count differs: " + name)
            for index, frame in enumerate(frames):
                expected = f"{index:04d}-{frame['native_frame']}.png"
                if names[index] != expected:
                    raise ValueError("original camera frame identity differs: " + name)
                (png_root / f"{index:04d}.png").write_bytes(archive.read(expected))
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                        "-framerate", "20", "-i", str(png_root / "%04d.png"),
                        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                        "-pix_fmt", "yuv420p", str(destination)],
                       check=True, capture_output=True, text=True, timeout=900)
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
                            "-select_streams", "v:0",
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
    """Require closed graph, restored world and four full original camera encodes."""
    destination = Path(destination)
    original = destination / "original-attempt"
    inventory = audit(original, case_id)
    graph = getattr(operator, "pipeline_capture", None)
    if graph is None or not graph.closed or graph.meta.get("extraction_confirmed") is not True:
        raise ValueError("original graph extraction was not confirmed")
    restoration = operator.verify_restoration()
    if not isinstance(restoration, dict) or restoration.get("restored") is not True:
        raise ValueError("Native world restoration readback missing")
    frames = json.loads((original / "frame-map.json").read_text())["frames"]
    trace = _rows(destination / "trace.jsonl")
    if len(frames) != 900 or len(trace) != 900:
        raise ValueError("original graph and parked activity frame counts differ")
    mapping = []
    for index, (frame, row) in enumerate(zip(frames, trace)):
        if (row.get("frame") != frame["native_frame"] or
                abs(row.get("time_s", -1) - frame["native_time_s"]) > 1e-6):
            raise ValueError("original graph and parked activity frame join differs")
        mapping.append({"video_frame": index, "carla_frame": frame["native_frame"],
                        "native_frame": frame["native_frame"], "time_s": frame["native_time_s"]})
    (destination / "video_frames.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in mapping))
    config = json.loads((destination / "config.json").read_text())
    camera_sizes = {item["name"]: (item["width"], item["height"])
                    for item in config["cameras"]}
    if set(camera_sizes) != set(VIEWS):
        raise ValueError("four camera definitions differ")
    codes = {}
    for name in VIEWS:
        width, height = camera_sizes[name]
        _encode_view(original / (name + ".zip"), destination / (name + ".mkv"),
                     name, frames, width, height)
        codes[name] = 0
    if inventory["diagnostic_fixture"] is False and not getattr(operator, "native_attested", False):
        raise ValueError("original operator attestation differs")
    (destination / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "native", "diagnostic_fixture": inventory["diagnostic_fixture"],
        "original_activity_sha256": inventory["activity_sha256"],
        "physical_acceptance_claimed": False}, indent=2, sort_keys=True) + "\n")
    from worker_exchange.native_output import seal_capture
    seal = seal_capture(destination, frames=900, restoration=restoration, errors=[],
                        encoder_exit_codes=codes,
                        context={"original_activity_sha256": inventory["activity_sha256"],
                                 "case_id": case_id})
    return {"case_id": case_id, "capture_seal_sha256": _sha(destination / "capture-seal.json"),
            "original_activity_sha256": inventory["activity_sha256"],
            "source_digest": seal["source_digest"], "diagnostic_fixture": inventory["diagnostic_fixture"],
            "physical_acceptance_claimed": False}
