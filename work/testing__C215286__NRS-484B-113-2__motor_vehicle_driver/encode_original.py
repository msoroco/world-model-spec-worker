"""Losslessly encode source-checked Native camera frames and primary mosaic."""

import hashlib
import json
import subprocess
from pathlib import Path

from carla_cameras import SIZES
from site_packet import VIEWS, verify_saved


def digest(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def validate_capture(capture, case_id, *, frames=900):
    """Reopen every original frame and station before invoking an encoder."""
    root = Path(capture)
    context_path = root / "reviewed-crosswalk-source.json"
    history_path = root / "channels/reverse-body-crosswalk.jsonl"
    mapping_path = root / "video_frames.jsonl"
    for path in (context_path, history_path, mapping_path):
        if not path.is_file():
            raise ValueError("Missing required source: " + str(path.relative_to(root)))
    context = json.loads(context_path.read_text())
    verify_saved(root, context)
    if context.get("source_id", "").split(":native:")[0] != case_id:
        raise ValueError("original capture exact case differs")
    if digest(history_path) != context.get("frames_sha256"):
        raise ValueError("original reverse frame bytes changed")
    rows, mapping = _lines(history_path), _lines(mapping_path)
    if len(rows) != frames or len(mapping) != frames:
        raise ValueError("complete original frame interval required")
    sensors = None
    for index, (row, frame) in enumerate(zip(rows, mapping)):
        native = frame.get("native_frame")
        if (row.get("frame") != index or frame.get("video_frame") != index
                or type(native) is not int or frame.get("carla_frame") != native
                or row.get("native_frame") != native or
                abs(row.get("time_s", -1) - index / 20) > .001 or
                abs(frame.get("time_s", -1) - index / 20) > .001):
            raise ValueError("original 20 Hz frame identity join differs")
        sources = frame.get("camera_sources", {})
        if set(sources) != set(VIEWS):
            raise ValueError("four original camera references missing")
        found = {name: sources[name].get("source_sensor") for name in VIEWS}
        if any(not value for value in found.values()) or len(set(found.values())) != len(VIEWS):
            raise ValueError("four distinct original camera sensors required")
        if sensors is None:
            sensors = found
        if sensors != found:
            raise ValueError("original camera sensor identity changed")
        for name in VIEWS:
            item = sources[name]
            expected = f"cameras/{name}/{index:04d}.png"
            path = root / expected
            if item.get("path") != expected or not path.is_file() or digest(path) != item.get("sha256"):
                raise ValueError("original camera bytes changed: " + name)
    return {"frames": frames, "map_sha256": context["map_packet"]["map_sha256"],
            "original_history_sha256": digest(history_path),
            "original_mapping_sha256": digest(mapping_path),
            "camera_sensors": sensors}


def _probe(path, frames, width, height, ffprobe):
    command = [ffprobe, "-v", "error", "-count_frames", "-select_streams", "v:0",
               "-show_entries", "stream=nb_read_frames,r_frame_rate,codec_name,width,height",
               "-of", "json", str(path)]
    completed = subprocess.run(command, check=True, capture_output=True, text=True, timeout=120)
    streams = json.loads(completed.stdout).get("streams", [])
    if len(streams) != 1:
        raise ValueError("single encoded video stream required")
    stream = streams[0]
    if (stream.get("nb_read_frames") != str(frames) or stream.get("r_frame_rate") != "20/1"
            or stream.get("codec_name") != "ffv1" or stream.get("width") != width
            or stream.get("height") != height):
        raise ValueError("full lossless video frame/rate/dimension readback differs")


def _decode(path, ffmpeg):
    command = [ffmpeg, "-v", "error", "-xerror", "-i", str(path),
               "-map", "0:v:0", "-f", "null", "-"]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=900)
    if completed.returncode:
        raise ValueError("full original video decode failed: " + completed.stderr[-500:])


def encode(attempt, case_id, *, frames=900, ffmpeg="ffmpeg", ffprobe="ffprobe"):
    root = Path(attempt)
    capture = root / "capture"
    checked = validate_capture(capture, case_id, frames=frames)
    encoded = {}
    for name in VIEWS:
        target = root / (name + ".mkv")
        if target.exists():
            raise ValueError("retain prior encoded original")
        pattern = capture / "cameras" / name / "%04d.png"
        command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin",
                   "-framerate", "20", "-start_number", "0", "-i", str(pattern),
                   "-frames:v", str(frames), "-c:v", "ffv1", "-level", "3",
                   "-pix_fmt", "bgr0", str(target)]
        subprocess.run(command, check=True, capture_output=True, timeout=900)
        _probe(target, frames, *SIZES[name], ffprobe)
        _decode(target, ffmpeg)
        encoded[name] = {"path": target.name, "sha256": digest(target),
                         "frames": frames, "fps": 20, "codec": "ffv1",
                         "source_sensor": checked["camera_sensors"][name]}
    primary = root / "raw.mkv"
    if primary.exists():
        raise ValueError("retain prior composed primary video")
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin"]
    for name in VIEWS:
        command += ["-i", str(root / (name + ".mkv"))]
    command += ["-filter_complex",
                "[0:v][1:v][2:v][3:v]xstack=inputs=4:layout=960_0|0_1080|1280_1080|2560_1080:fill=black[v]",
                "-map", "[v]", "-frames:v", str(frames), "-c:v", "ffv1", "-level", "3",
                "-pix_fmt", "bgr0", str(primary)]
    subprocess.run(command, check=True, capture_output=True, timeout=900)
    _probe(primary, frames, 3840, 1800, ffprobe)
    _decode(primary, ffmpeg)
    encoded["primary"] = {"path": primary.name, "sha256": digest(primary),
                          "frames": frames, "fps": 20, "codec": "ffv1",
                          "layout": "overview above three unscaled detail views"}
    index = {"format": "c215286-original-lossless-video", "case_id": case_id,
             "capture": checked, "views": encoded,
             "actual_pixels_reviewed": False, "legal_judgment": "unresolved"}
    with (root / "encoded-views.json").open("x") as stream:
        json.dump(index, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return index
