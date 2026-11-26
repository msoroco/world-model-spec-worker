"""Independently verify a saved four-camera Native signal acquisition.

This verifies source identity and decode. It does not accept the scene, pixels,
physical turn, statutory district, or legal signal distance.
"""
from __future__ import annotations

import argparse
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
from zipfile import ZipFile

from PIL import Image

from native_capture_contract import CAMERAS, DIMENSIONS, FRAMES, STEP_S
from native_site import validate


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def audit(directory: str | Path, case_id: str, *, allow_diagnostic: bool = False) -> dict:
    root = Path(directory)
    receipt_path = root / "original-acquisition-receipt.json"
    receipt_raw = receipt_path.read_bytes()
    receipt = json.loads(receipt_raw)
    _require(receipt.get("format") == "original-turn-signal-acquisition" and
             receipt.get("case_id") == case_id, "wrong acquisition receipt identity")
    _require(receipt.get("physical_acceptance") is False and
             receipt.get("legal_assessment") == "unresolved", "premature acceptance claim")
    site_raw = (root / "original-site.json").read_bytes()
    _require(_sha(site_raw) == receipt.get("site_sha256"), "original site hash differs")
    site = json.loads(site_raw)
    validate(site, case_id.rsplit("__", 1)[-1], allow_diagnostic=allow_diagnostic)
    trace_raw = (root / "original-turn-signal.json").read_bytes()
    _require(_sha(trace_raw) == receipt.get("trace_sha256"), "original trace hash differs")
    trace = json.loads(trace_raw)
    diagnostic = trace.get("diagnostic_fixture") is True
    _require(not diagnostic or allow_diagnostic, "diagnostic fixture is not original")
    _require(trace.get("source_kind") == ("diagnostic_fixture" if diagnostic else "original_native"),
             "trace provenance differs")
    _require(trace.get("case_id") == case_id and trace.get("site_sha256") ==
             receipt.get("site_sha256"), "trace source identity differs")
    rows = trace.get("samples")
    count = receipt.get("frame_count")
    _require(type(count) is int and count > 0 and isinstance(rows, list) and
             len(rows) == count and trace.get("frame_count") == count,
             "trace frame count differs")
    _require(diagnostic or count == FRAMES, "original 900-frame capture incomplete")
    _require(trace.get("sampling_hz") == 20 and set(trace.get("camera_archives", {})) ==
             set(CAMERAS) and set(receipt.get("camera_archives", {})) == set(CAMERAS),
             "four-camera acquisition incomplete")
    previous = None
    for row in rows:
        frame, time_s = row.get("frame"), row.get("time_s")
        _require(type(frame) is int and type(time_s) in (int, float) and
                 math.isfinite(time_s) and set(row.get("camera_frames", {})) == set(CAMERAS),
                 "original frame or camera join missing")
        if not diagnostic:
            vertices = row.get("body_vertices_m")
            _require(isinstance(vertices, list) and len(vertices) == 8 and
                     all(isinstance(point, list) and len(point) == 2 and
                         all(type(value) in (int, float) and math.isfinite(value)
                             for value in point) for point in vertices),
                     "original ego body vertices missing")
        if previous is not None:
            _require(frame == previous[0] + 1 and abs(time_s - previous[1] - STEP_S) <= 1e-4,
                     "original frame or 20 Hz time gap")
        previous = (frame, time_s)
    archive_hashes = {}
    for name in CAMERAS:
        descriptor = receipt["camera_archives"][name]
        _require(descriptor == trace["camera_archives"][name] and
                 descriptor.get("path") == name + ".png.zip" and
                 descriptor.get("frame_count") == count and
                 descriptor.get("dimensions") == list(DIMENSIONS[name]),
                 "camera archive declaration differs: " + name)
        archive = root / descriptor["path"]
        raw = archive.read_bytes()
        _require(_sha(raw) == descriptor.get("sha256"), "camera archive hash differs: " + name)
        with ZipFile(BytesIO(raw)) as stream:
            names = stream.namelist()
            expected = [f"{row['frame']:08d}.png" for row in rows]
            _require(names == expected, "camera frame membership differs: " + name)
            for row, member in zip(rows, names):
                data = stream.read(member)
                declared = row["camera_frames"][name]
                _require(declared == {"member": member, "sha256": _sha(data)},
                         "camera frame source hash differs: " + name)
                with Image.open(BytesIO(data)) as image:
                    image.load()
                    _require(image.format == "PNG" and image.size == DIMENSIONS[name],
                             "camera PNG decode or dimensions differ: " + name)
        archive_hashes[name] = descriptor["sha256"]
    return {"format": "turn-signal-saved-source-audit", "case_id": case_id,
            "diagnostic_fixture": diagnostic, "frame_count": count,
            "receipt_sha256": _sha(receipt_raw), "site_sha256": _sha(site_raw),
            "trace_sha256": _sha(trace_raw), "camera_archive_sha256": archive_hashes,
            "source_decode_passed": True, "physical_acceptance_claimed": False,
            "legal_assessment": "unresolved"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = audit(args.attempt, args.case_id)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
