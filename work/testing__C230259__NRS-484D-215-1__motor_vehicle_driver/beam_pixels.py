"""Original pixel measurements of persons, vehicles, and oncoming eye region.

Frame-specific ROIs must be sourced from reviewed original camera calibration
and participant projection. RGB luma is an image observable, never calibrated
illuminance, safe revelation, projected glare rays, or a legal conclusion.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile

from PIL import Image

VIEWS = ("approach", "driver_reference")
ROLES = {"person": "approach", "target_vehicle": "approach", "oncoming_eye": "driver_reference"}


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source(root: Path, name: str, digest: str) -> Path:
    if name != Path(name).name or name in ("", ".", ".."):
        raise ValueError("original pixel source must be attempt-relative")
    path = root / name
    if not path.is_file() or path.is_symlink() or _hash(path) != digest:
        raise ValueError("original pixel source missing or changed: " + name)
    return path


def _box(value, size, role):
    if (not isinstance(value, list) or len(value) != 4 or
            any(type(x) is not int for x in value)):
        raise ValueError("reviewed original ROI box missing: " + role)
    left, top, right, bottom = value
    if not (0 <= left < right <= size[0] and 0 <= top < bottom <= size[1]):
        raise ValueError("reviewed original ROI outside camera: " + role)
    if (right - left) * (bottom - top) < 4:
        raise ValueError("reviewed original ROI too small: " + role)
    return tuple(value)


def _luma(image, box):
    cropped = image.crop(box).convert("RGB")
    pixels = cropped.getdata()
    total = 0.0
    for red, green, blue in pixels:
        total += .2126 * red + .7152 * green + .0722 * blue
    return round(total / len(pixels), 4)


def measure(root: Path, source_hashes: dict[str, str], *, expected_frames: int = 900,
            diagnostic: bool = False, include_eye: bool = True) -> dict:
    root = Path(root)
    common = {"roi-frames.jsonl", "camera-frame-map.jsonl"}
    zipped = {"approach.zip", "driver_reference.zip"}
    movies = {"approach.mkv", "driver_reference.mkv"}
    if set(source_hashes) not in (common | zipped, common | movies):
        raise ValueError("original ROI, camera and frame-map hashes required")
    sources = {name: _source(root, name, source_hashes[name]) for name in source_hashes}
    rois = [json.loads(x) for x in sources["roi-frames.jsonl"].read_text().splitlines() if x]
    frame_map = [json.loads(x) for x in sources["camera-frame-map.jsonl"].read_text().splitlines() if x]
    if len(rois) != expected_frames or len(frame_map) != expected_frames or expected_frames < 2:
        raise ValueError("complete original frame-specific ROI join required")
    roles = {"person", "target_vehicle", "oncoming_eye"} if include_eye else {"person", "target_vehicle"}
    result = []
    for index, (roi, mapped) in enumerate(zip(rois, frame_map)):
        frame = mapped.get("frame")
        if type(frame) is not int or frame != frame_map[0].get("frame") + index or roi.get("frame") != frame:
            raise ValueError("original ROI frame identity differs")
        if roi.get("source_kind") != "reviewed_original_projection" or roi.get("diagnostic_fixture") is not diagnostic:
            raise ValueError("reviewed original projected ROI source required")
        if not diagnostic and (not roi.get("calibration_source_sha256") or not roi.get("projection_source_sha256")):
            raise ValueError("original projection/calibration source hash required")
        if not isinstance(roi.get("regions"), dict) or set(roi["regions"]) != roles:
            raise ValueError("person, vehicle and required oncoming-eye ROIs required")
        for view in VIEWS:
            if mapped.get(view + "_source_frame") != frame:
                raise ValueError("stale original camera frame join: " + view)
        result.append({"original_frame": frame})

    use_movie = set(source_hashes) == common | movies
    for view in VIEWS:
        expected_size = ((1280, 720) if use_movie else (16, 12)) if diagnostic else (1280, 720)
        if use_movie:
            path = sources[view + ".mkv"]
            command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                       "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"]
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                size = expected_size[0] * expected_size[1] * 3
                for index in range(expected_frames):
                    raw = process.stdout.read(size)
                    if len(raw) != size:
                        raise ValueError("original movie decoded fewer frames: " + view)
                    image = Image.frombytes("RGB", expected_size, raw)
                    for role in roles:
                        if ROLES[role] == view:
                            result[index][role + "_mean_luma_8bit"] = _luma(
                                image, _box(rois[index]["regions"][role], expected_size, role))
                if process.stdout.read(1):
                    raise ValueError("original movie decoded extra frames: " + view)
                error = process.stderr.read().decode("utf-8", errors="replace")
                if process.wait() != 0:
                    raise ValueError("original movie decode failed: " + view + ": " + error[-300:])
            except BaseException:
                process.kill()
                process.wait()
                raise
            finally:
                process.stdout.close()
                process.stderr.close()
        else:
            with ZipFile(sources[view + ".zip"]) as archive:
                expected_names = [str(row["frame"]) + ".png" for row in frame_map]
                if archive.namelist() != expected_names or len(set(archive.namelist())) != expected_frames:
                    raise ValueError("original camera archive frame inventory differs: " + view)
                for index, name in enumerate(expected_names):
                    with Image.open(io.BytesIO(archive.read(name))) as source_image:
                        if source_image.format != "PNG" or source_image.size != expected_size:
                            raise ValueError("original RGB PNG camera profile differs")
                        image = source_image.convert("RGB")
                    for role in roles:
                        if ROLES[role] == view:
                            result[index][role + "_mean_luma_8bit"] = _luma(
                                image, _box(rois[index]["regions"][role], expected_size, role))
    return {"format": "beam-road-original-pixels-v1", "frame_count": expected_frames,
            "source_hashes": source_hashes, "rows": result,
            "calibrated_illuminance_claimed": False, "physical_glare_claimed": False,
            "legal_verdict_claimed": False}
