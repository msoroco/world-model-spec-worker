"""Saved-only crossing-entry result from an original source-sealed attempt.

The fixed yield-sign cell does not establish subsection 4's inoperative signal.
Original device evidence and any final legal applicability review remain open.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from crossing_timing import REQUIRED, measure
from native_history_capture import CAMERAS, audit_media


def finalize(attempt, output, *, expected_manifest_sha256, probe_id):
    attempt, output = Path(attempt), Path(output)
    if probe_id not in ("entry_below", "entry_inside", "entry_above"):
        raise ValueError("unknown exact timing probe")
    manifest_path = attempt / "source-manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != expected_manifest_sha256:
        raise ValueError("original source manifest hash mismatch")
    manifest = json.loads(manifest_bytes)
    if not set(REQUIRED).issubset(manifest):
        raise ValueError("original source manifest incomplete")
    timing = measure(attempt)
    if timing["assignment_id"] != "testing__C125763__NRS-484B-250-2__motor_vehicle_driver":
        raise ValueError("wrong exact assignment")
    frame_count = sum(1 for line in (attempt / "ego-body-history.jsonl").read_text(
        encoding="utf-8").splitlines() if line.strip())
    site = json.loads((attempt / 'site-context.json').read_text(encoding='utf-8'))
    diagnostic_fixture = frame_count != 900 or site.get('review_status') != 'reviewed_original'
    media = None
    if 'camera-frame-map.jsonl' in manifest:
        dimensions = site.get('camera_dimensions')
        if not isinstance(dimensions, dict) or set(dimensions) != set(CAMERAS):
            raise ValueError('source-bound four-camera dimensions required')
        media = audit_media(attempt, camera_dimensions=dimensions)
        if media['joined_original_frames'] != frame_count:
            raise ValueError('saved camera and body frame count differs')
    result = {
        "format": "c125763-saved-entry-finalizer-v1",
        "assignment_id": timing["assignment_id"],
        "probe_id": probe_id,
        "source_manifest_sha256": expected_manifest_sha256,
        "source_sha256": timing["source_sha256"],
        "original_frame_count": frame_count,
        "rate_hz": 20,
        "timing": timing,
        "diagnostic_fixture": diagnostic_fixture,
        "camera_coverage_verified": media is not None,
        "camera_audit": media,
        "physical_acceptance": False,
        "legal_verdict_claimed": False,
    }
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result
