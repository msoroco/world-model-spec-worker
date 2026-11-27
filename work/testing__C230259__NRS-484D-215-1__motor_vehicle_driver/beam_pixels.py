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
    names = {"roi-frames.jsonl", "approach.zip", "driver_reference.zip", "camera-frame-map.jsonl"}
    if set(source_hashes) != names:
        raise ValueError("original ROI, camera and frame-map hashes required")
    sources = {name: _source(root, name, source_hashes[name]) for name in names}
    rois = [json.loads(x) for x in sources["roi-frames.jsonl"].read_text().splitlines() if x]
    frame_map = [json.loads(x) for x in sources["camera-frame-map.jsonl"].read_text().splitlines() if x]
    if len(rois) != expected_frames or len(frame_map) != expected_frames or expected_frames < 2:
        raise ValueError("complete original frame-specific ROI join required")
    result = []
    with ZipFile(sources["approach.zip"]) as approach, ZipFile(sources["driver_reference.zip"]) as eye_view:
        archives = {"approach": approach, "driver_reference": eye_view}
        expected_names = [str(row.get("frame")) + ".png" for row in frame_map]
        for view, archive in archives.items():
            if archive.namelist() != expected_names or len(set(archive.namelist())) != expected_frames:
                raise ValueError("original camera archive frame inventory differs: " + view)
        for index, (roi, mapped) in enumerate(zip(rois, frame_map)):
            frame = mapped.get("frame")
            if type(frame) is not int or frame != frame_map[0].get("frame") + index or roi.get("frame") != frame:
                raise ValueError("original ROI frame identity differs")
            if roi.get("source_kind") != "reviewed_original_projection" or roi.get("diagnostic_fixture") is not diagnostic:
                raise ValueError("reviewed original projected ROI source required")
            if not diagnostic and (not roi.get("calibration_source_sha256") or not roi.get("projection_source_sha256")):
                raise ValueError("original projection/calibration source hash required")
            regions = roi.get("regions")
            roles = {"person", "target_vehicle", "oncoming_eye"} if include_eye else {"person", "target_vehicle"}
            if not isinstance(regions, dict) or set(regions) != roles:
                raise ValueError("person, vehicle and required oncoming-eye ROIs required")
            opened = {}
            for view, archive in archives.items():
                if mapped.get(view + "_source_frame") != frame:
                    raise ValueError("stale original camera frame join: " + view)
                with Image.open(io.BytesIO(archive.read(str(frame) + ".png"))) as image:
                    expected_size = (16, 12) if diagnostic else (1280, 720)
                    if image.format != "PNG" or image.size != expected_size:
                        raise ValueError("original RGB PNG camera profile differs")
                    opened[view] = image.convert("RGB")
            observed = {}
            for role in roles:
                view = ROLES[role]
                box = _box(regions[role], opened[view].size, role)
                observed[role + "_mean_luma_8bit"] = _luma(opened[view], box)
            result.append({"original_frame": frame, **observed})
    return {"format": "beam-road-original-pixels-v1", "frame_count": expected_frames,
            "source_hashes": source_hashes, "rows": result,
            "calibrated_illuminance_claimed": False, "physical_glare_claimed": False,
            "legal_verdict_claimed": False}
