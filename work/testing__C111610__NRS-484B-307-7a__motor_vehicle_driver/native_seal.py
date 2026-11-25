"""Seal source-derived Native trace, frame map and four lossless camera videos."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from zipfile import ZipFile

from native_camera_capture import CAMERAS


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_rows(path, rows):
    with Path(path).open("x") as stream:
        for row in rows:
            stream.write(json.dumps(row, allow_nan=False, separators=(",", ":")) + "\n")


def seal(attempt):
    """Run only after CARLA actors and synchronous settings have been restored."""
    from worker_exchange.native_output import seal_capture

    attempt = Path(attempt).resolve()
    events = json.loads((attempt / "arrow-events-original.json").read_text())
    aspects = json.loads((attempt / "arrow-aspect-original.json").read_text())
    cameras = json.loads((attempt / "arrow-camera-receipt.json").read_text())
    if len(events) != 900 or len(aspects) != 900 or cameras.get("frame_count") != 900:
        raise ValueError("original Native capture lacks 900 synchronized frames")
    trace, mapping, body_history = [], [], []
    for index, (event, aspect) in enumerate(zip(events, aspects)):
        frame, time_s = aspect["frame"], aspect["elapsed_seconds"]
        if event["frame"] != frame:
            raise ValueError("original Native trace/aspect frame mismatch")
        xy = event["ego_xy"]
        trace.append({"frame": frame, "time_s": time_s,
                      "position": {"x": xy[0], "y": xy[1], "z": event["ego_z_m"]},
                      "position_m": [xy[0], xy[1], event["ego_z_m"]],
                      "heading_deg": event["ego_heading_deg"],
                      "speed_mps": event["ego_speed_mps"],
                      "control": {"brake": event["ego_brake"]}})
        mapping.append({"video_frame": index, "carla_frame": frame,
                        "native_frame": frame, "time_s": time_s})
        body_history.append({"frame": frame, "time_s": time_s,
                             "body_vertices_m": event["ego_body_vertices_m"],
                             "heading_deg": event["ego_heading_deg"]})
    _write_rows(attempt / "trace.jsonl", trace)
    _write_rows(attempt / "video_frames.jsonl", mapping)
    _write_rows(attempt / "body_history.jsonl", body_history)
    for name in CAMERAS:
        source = cameras["camera_sources"][name]
        archive = attempt / source["path"]
        if _sha(archive) != source["sha256"]:
            raise ValueError("original camera archive changed before video projection")
        output = attempt / (name + ".mkv")
        if output.exists():
            raise ValueError("derived camera video already exists")
        command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                   "-f", "image2pipe", "-framerate", "20", "-vcodec", "png",
                   "-i", "pipe:0", "-an", "-c:v", "ffv1", "-threads", "1",
                   "-fflags", "+bitexact", "-flags:v", "+bitexact", str(output)]
        process = subprocess.Popen(command, stdin=subprocess.PIPE,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            with ZipFile(archive) as zip_file:
                expected = {f"{row['carla_frame']:08d}.png" for row in mapping}
                if set(zip_file.namelist()) != expected or len(zip_file.namelist()) != 900:
                    raise ValueError("original camera archive frame count changed")
                for row in mapping:
                    member = f"{row['carla_frame']:08d}.png"
                    process.stdin.write(zip_file.read(member))
            process.stdin.close()
            errors = process.stderr.read()
            if process.wait(timeout=300) != 0:
                raise ValueError("lossless camera projection failed: " + errors.decode(errors="replace")[-1000:])
        except BaseException:
            process.kill()
            process.wait()
            output.unlink(missing_ok=True)
            raise
        finally:
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
            if process.stderr:
                process.stderr.close()
        if _sha(archive) != source["sha256"]:
            raise ValueError("original camera archive changed during projection")
    (attempt / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "native", "diagnostic_fixture": False,
        "physical_acceptance_claimed": False}, sort_keys=True) + "\n")
    return seal_capture(attempt, frames=900, restoration={"restored": True,
                        "method": "world settings and actors restored by runner finally"},
                        errors=[], encoder_exit_codes={name: 0 for name in CAMERAS})
