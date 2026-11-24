"""Saved-only crossing-entry result from an original source-sealed attempt.

The exact legal applicability at this yield-sign cell remains unresolved.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from crossing_timing import REQUIRED, measure


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
    result = {
        "format": "c125763-saved-entry-finalizer-v1",
        "assignment_id": timing["assignment_id"],
        "probe_id": probe_id,
        "source_manifest_sha256": expected_manifest_sha256,
        "source_sha256": timing["source_sha256"],
        "original_frame_count": frame_count,
        "rate_hz": 20,
        "timing": timing,
        "diagnostic_fixture": frame_count != 900,
        "camera_coverage_verified": False,
        "physical_acceptance": False,
        "legal_verdict_claimed": False,
    }
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result
