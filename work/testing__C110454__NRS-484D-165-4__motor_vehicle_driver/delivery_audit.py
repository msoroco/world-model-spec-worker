"""Independent saved-source integrity audit for the three parked-lamp cases.

This checks acquisition identity and sealed files. Video decoding and the
physical interpretation of emitted light remain separate review steps.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import zipfile

from PIL import Image

from lamp_probe import CASE_MODES
from saved_lamps import process_saved


ASSIGNMENT = "testing__C110454__NRS-484D-165-4__motor_vehicle_driver"
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
EXPECTED_FRAMES = 900  # 45 seconds at the pinned 20 Hz acquisition cadence.
PROFILE = {"overview": (1920, 1080), "approach": (1280, 720),
           "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _contained(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("media path must be attempt relative")
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise ValueError("media path missing or escapes attempt")
    return target


def decode_original_cameras(paths: dict, camera_rows: list, *, dimensions=None) -> dict:
    """Decode every original frame at the exact Native frame identity."""
    sizes = PROFILE if dimensions is None else dimensions
    if set(paths) != set(VIEWS) or set(sizes) != set(VIEWS) or not camera_rows:
        raise ValueError("four original camera archives and frame rows required")
    frames = [row.get("frame") for row in camera_rows]
    if any(type(frame) is not int for frame in frames) or frames != list(range(frames[0], frames[0] + len(frames))):
        raise ValueError("original camera frame sequence invalid")
    counts = {}
    for view in VIEWS:
        with zipfile.ZipFile(paths[view]) as archive:
            names = archive.namelist()
            expected = [f"{frame}.png" for frame in frames]
            if len(names) != len(set(names)) or set(names) != set(expected):
                raise ValueError("original camera ZIP frame inventory differs: " + view)
            for frame, name in zip(frames, expected):
                row = camera_rows[frame - frames[0]]
                if row.get(view + "_source_frame") != frame:
                    raise ValueError("original camera frame map differs: " + view)
                with Image.open(io.BytesIO(archive.read(name))) as image:
                    if image.format != "PNG" or image.size != tuple(sizes[view]):
                        raise ValueError("original camera PNG profile differs: " + view)
                    image.load()
        counts[view] = len(frames)
    return counts


def audit(attempt: Path, manifest_path: Path, *, case_id: str,
          allow_diagnostic: bool = False) -> dict:
    """Audit one attempt's exact case, Native histories, and four media seals.

    The manifest is authored after capture and binds paths, hashes, source
    receipt, source map, and media. `allow_diagnostic` is only for CPU fixtures.
    """
    if case_id not in {ASSIGNMENT + "__" + mode for mode in CASE_MODES}:
        raise ValueError("unknown exact case ID")
    root = Path(attempt).resolve()
    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text())
    if manifest.get("format") != "parked-headlamp-acquisition-v1" or manifest.get("case_id") != case_id:
        raise ValueError("saved acquisition case identity mismatch")
    if manifest.get("acquisition_kind") != "native" and not allow_diagnostic:
        raise ValueError("delivery requires Native acquisition")
    if manifest.get("physical_acceptance_claimed") is not False:
        raise ValueError("saved acquisition must not claim physical acceptance")
    receipt_record = manifest.get("native_receipt", {})
    receipt = _contained(root, receipt_record.get("path"))
    if _sha(receipt) != receipt_record.get("sha256"):
        raise ValueError("Native receipt hash changed")
    saved = process_saved(root, receipt, receipt_record["sha256"], case_id=case_id,
                          allow_diagnostic=allow_diagnostic)
    measured = saved["observation"]
    if measured["frame_count"] != EXPECTED_FRAMES:
        raise ValueError("saved acquisition is shorter than planned 45 seconds")
    mode = case_id.rsplit("__", 1)[1]
    if measured["parked_sample_count"] != EXPECTED_FRAMES:
        raise ValueError("parked footprint/brake/stationary observation incomplete")
    if mode == "unlit" and (measured["low_beam_readback_count"] or measured["high_beam_readback_count"]):
        raise ValueError("unlit readback differs from requested probe")
    if mode == "low_beam" and (measured["low_beam_readback_count"] != EXPECTED_FRAMES or measured["high_beam_readback_count"]):
        raise ValueError("low-beam readback differs from requested probe")
    if mode == "high_beam" and (measured["high_beam_readback_count"] != EXPECTED_FRAMES or measured["low_beam_readback_count"]):
        raise ValueError("high-beam readback differs from requested probe")
    media = manifest.get("media")
    if not isinstance(media, dict) or set(media) != set(VIEWS):
        raise ValueError("four exact original camera media sources required")
    media_hashes = {}
    media_paths = set()
    original_paths = {}
    for view in VIEWS:
        item = media[view]
        if not isinstance(item, dict) or item.get("source_frame_count") != EXPECTED_FRAMES:
            raise ValueError("camera source frame count missing")
        path = _contained(root, item.get("path"))
        if path in media_paths:
            raise ValueError("camera sources must be distinct")
        media_paths.add(path)
        digest = _sha(path)
        if path.stat().st_size == 0 or digest != item.get("sha256"):
            raise ValueError("original camera media hash changed or empty")
        media_hashes[view] = digest
        original_paths[view] = path
    decoded = None
    if not allow_diagnostic:
        camera_rows = [json.loads(line) for line in
                       (root / "camera-frame-map.jsonl").read_text().splitlines()]
        decoded = decode_original_cameras(original_paths, camera_rows)
        if any(count != EXPECTED_FRAMES for count in decoded.values()):
            raise ValueError("original camera decode frame count incomplete")
    return {"format": "parked-headlamp-delivery-integrity-v1", "case_id": case_id,
            "native_receipt_sha256": receipt_record["sha256"],
            "source_hashes": measured["source_hashes"], "media_hashes": media_hashes,
            "frame_count": EXPECTED_FRAMES, "saved_source_integrity_passed": True,
            "observation": measured,
            "full_video_decode_passed": decoded is not None,
            "decoded_frames_per_camera": decoded,
            "emission_and_aim_reviewed": False,
            "physical_acceptance_claimed": False}
