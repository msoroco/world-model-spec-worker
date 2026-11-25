"""Record and independently audit four original camera streams for C158208.

The Native owner passes the actual sensor PNG bytes for each world tick.  A
saved-only audit reopens every archive and decodes every image.  Neither path
asserts that the statutory sign or participant is visually legible.
"""

from __future__ import annotations

import hashlib
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

from PIL import Image

from source_tick_capture import verify_seal


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
ASSIGNMENT = "testing__C158208__NRS-484B-257-1__motor_vehicle_driver"
DIMENSIONS = {"overview": (1920, 1080), "approach": (1280, 720),
              "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _decode(data: bytes, dimensions: tuple[int, int]) -> None:
    with Image.open(BytesIO(data)) as image:
        image.verify()
    with Image.open(BytesIO(data)) as image:
        if image.format != "PNG" or image.size != dimensions:
            raise ValueError("original camera PNG format or dimensions differ")
        image.load()


def _verify_raw_bgra_hash(data: bytes, expected: str, name: str) -> None:
    """Prove the archived lossless PNG reconstructs the original opaque BGRA."""
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError(f"{name} original BGRA source hash missing")
    with Image.open(BytesIO(data)) as image:
        reconstructed = image.convert("RGBA").tobytes("raw", "BGRA")
    if _sha(reconstructed) != expected:
        raise ValueError(f"{name} original BGRA source hash differs")


def _safe_file(attempt: Path, name: str) -> Path:
    if not isinstance(name, str) or Path(name).name != name or not name:
        raise ValueError("camera source path must be a direct attempt child")
    return attempt / name


def _identity(attempt: Path, diagnostic_fixture: bool) -> tuple[dict, str]:
    path = attempt / "capture-identity.json"
    data = path.read_bytes()
    identity = json.loads(data)
    if identity.get("format") != "c158208-original-capture-identity-v1":
        raise ValueError("original capture identity format differs")
    if identity.get("assignment_id") != ASSIGNMENT or identity.get("case_id") not in (
            ASSIGNMENT + "__nearest_view_response", ASSIGNMENT + "__nearest_view_uninterrupted"):
        raise ValueError("original capture identity case differs")
    if identity.get("provenance_kind") != ("synthetic_fixture" if diagnostic_fixture else "original_capture"):
        raise ValueError("original capture identity provenance differs")
    if identity.get("original_tick_seal_sha256") != _sha((attempt / "nearest-view-tick-seal.json").read_bytes()):
        raise ValueError("original capture identity tick seal differs")
    return identity, _sha(data)


def write_camera_sources(attempt: Path, frames: list[dict], *,
                         diagnostic_fixture: bool = False) -> dict:
    """Seal synchronized original PNG bytes supplied by four Native sensors.

    Each frame has ``frame``, ``time_s`` and ``cameras`` mapping camera names to
    unmodified PNG bytes.  Existing attempt media is never overwritten.
    """
    attempt = Path(attempt)
    packet = verify_seal(attempt)
    identity, identity_sha = _identity(attempt, diagnostic_fixture)
    samples = packet["samples"]
    raw_rows = [json.loads(line) for line in (attempt / "nearest-view-original-ticks.jsonl").read_text().splitlines()]
    if len(frames) != len(samples) or (not diagnostic_fixture and len(frames) != 900):
        raise ValueError("camera count differs from 900-frame original tick source")
    dimensions = {name: DIMENSIONS[name] if not diagnostic_fixture else (8, 6)
                  for name in CAMERAS}
    manifest_path = attempt / "nearest-view-camera-manifest.json"
    archives = {name: attempt / f"nearest-view-{name}-original-png.zip" for name in CAMERAS}
    if manifest_path.exists() or any(path.exists() for path in archives.values()):
        raise ValueError("original camera attempt already used")
    rows = []
    for frame, sample in zip(frames, samples):
        if frame.get("frame") != sample["frame"] or frame.get("time_s") != sample["time_s"]:
            raise ValueError("camera frame/time differs from original world tick")
        sources = frame.get("cameras")
        if not isinstance(sources, dict) or set(sources) != set(CAMERAS):
            raise ValueError("four original cameras required for every tick")
        row = {"frame": sample["frame"], "time_s": sample["time_s"], "cameras": {}}
        raw_hashes = raw_rows[len(rows)].get("camera_raw_bgra_sha256")
        if not diagnostic_fixture and (not isinstance(raw_hashes, dict) or set(raw_hashes) != set(CAMERAS)):
            raise ValueError("four original BGRA camera hashes required")
        for name in CAMERAS:
            data = sources[name]
            if not isinstance(data, bytes):
                raise ValueError("original camera source must be PNG bytes")
            _decode(data, dimensions[name])
            if isinstance(raw_hashes, dict) and name in raw_hashes:
                _verify_raw_bgra_hash(data, raw_hashes[name], name)
            row["cameras"][name] = _sha(data)
        rows.append(row)
    for name, path in archives.items():
        with ZipFile(path, "x", compression=ZIP_STORED) as archive:
            for frame in frames:
                archive.writestr(f"{frame['frame']:08d}.png", frame["cameras"][name])
    manifest = {"format": "c158208-original-cameras-v1", "fps": 20,
                "case_id": identity["case_id"], "capture_identity_sha256": identity_sha,
                "provenance_kind": "synthetic_fixture" if diagnostic_fixture else "original_capture",
                "tick_seal_sha256": _sha((attempt / "nearest-view-tick-seal.json").read_bytes()),
                "rows": rows,
                "sources": {name: {"path": path.name, "sha256": _sha(path.read_bytes()),
                                   "dimensions": list(dimensions[name])}
                            for name, path in archives.items()}}
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def audit_camera_sources(attempt: Path, *, diagnostic_fixture: bool = False) -> dict:
    """Saved-only full decode and frame/hash join against original sealed ticks."""
    attempt = Path(attempt)
    packet = verify_seal(attempt)
    identity, identity_sha = _identity(attempt, diagnostic_fixture)
    manifest_path = attempt / "nearest-view-camera-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != "c158208-original-cameras-v1" or manifest.get("fps") != 20:
        raise ValueError("original camera manifest format/fps differs")
    if manifest.get("provenance_kind") != ("synthetic_fixture" if diagnostic_fixture else "original_capture"):
        raise ValueError("camera provenance differs")
    if manifest.get("tick_seal_sha256") != _sha((attempt / "nearest-view-tick-seal.json").read_bytes()):
        raise ValueError("camera manifest tick seal differs")
    if manifest.get("case_id") != identity["case_id"] or manifest.get("capture_identity_sha256") != identity_sha:
        raise ValueError("camera manifest capture identity differs")
    samples = packet["samples"]
    raw_rows = [json.loads(line) for line in (attempt / "nearest-view-original-ticks.jsonl").read_text().splitlines()]
    rows = manifest.get("rows")
    if not isinstance(rows, list) or len(rows) != len(samples) or (not diagnostic_fixture and len(rows) != 900):
        raise ValueError("camera count differs from 900-frame original tick source")
    sources = manifest.get("sources")
    if not isinstance(sources, dict) or set(sources) != set(CAMERAS):
        raise ValueError("four original camera archives required")
    for row, sample in zip(rows, samples):
        if row.get("frame") != sample["frame"] or row.get("time_s") != sample["time_s"]:
            raise ValueError("saved camera row differs from original world tick")
        if not isinstance(row.get("cameras"), dict) or set(row["cameras"]) != set(CAMERAS):
            raise ValueError("saved camera row missing a view")
    for name in CAMERAS:
        source = sources[name]
        path = _safe_file(attempt, source.get("path"))
        if source.get("sha256") != _sha(path.read_bytes()):
            raise ValueError(f"{name} original archive hash differs")
        dimensions = DIMENSIONS[name] if not diagnostic_fixture else (8, 6)
        if source.get("dimensions") != list(dimensions):
            raise ValueError(f"{name} original dimensions differ")
        expected_members = [f"{sample['frame']:08d}.png" for sample in samples]
        with ZipFile(path) as archive:
            if archive.namelist() != expected_members:
                raise ValueError(f"{name} original camera frame map differs")
            for index, (member, row) in enumerate(zip(expected_members, rows)):
                data = archive.read(member)
                if _sha(data) != row["cameras"][name]:
                    raise ValueError(f"{name} original camera pixel hash differs")
                _decode(data, dimensions)
                raw_hashes = raw_rows[index].get("camera_raw_bgra_sha256")
                if not diagnostic_fixture and (not isinstance(raw_hashes, dict) or name not in raw_hashes):
                    raise ValueError(f"{name} original BGRA source hash missing")
                if isinstance(raw_hashes, dict) and name in raw_hashes:
                    _verify_raw_bgra_hash(data, raw_hashes[name], name)
    return {"format": "c158208-saved-camera-audit-v1", "frame_count": len(rows),
            "decoded_images": len(rows) * len(CAMERAS),
            "camera_manifest_sha256": _sha(manifest_path.read_bytes()),
            "physical_acceptance": False, "legal_status": "unresolved"}
