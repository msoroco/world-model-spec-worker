"""Independent closed-file audit for a captured passenger curb zone attempt."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def audit_original_history(path: Path, expected_sha256: str, case_id: str,
                           expected_zone_sha256: str, expected_regulations_sha256: str) -> dict:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise ValueError("original history hash mismatch")
    try:
        rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("original history decode failed") from exc
    if len(rows) != 900:
        raise ValueError("original frame count mismatch")
    first = rows[0].get("original_frame")
    if type(first) is not int:
        raise ValueError("original frame identity missing")
    fixed = ("ego_id", "passenger_id", "map_sha256", "zone_source_sha256",
             "regulations_source_sha256", "clock_source_sha256", "camera_plan_sha256")
    baseline = {key: rows[0].get(key) for key in fixed}
    if any(not value for value in baseline.values()):
        raise ValueError("fixed source or identity missing")
    if baseline["zone_source_sha256"] != expected_zone_sha256 or baseline["regulations_source_sha256"] != expected_regulations_sha256:
        raise ValueError("zone or regulation source mismatch")
    previous_time = None
    for offset, row in enumerate(rows):
        if row.get("case_id") != case_id or row.get("original_frame") != first + offset:
            raise ValueError("case/original frame join mismatch")
        if any(row.get(key) != value for key, value in baseline.items()):
            raise ValueError("fixed source changed")
        if not row.get("source_sha256") or not row.get("control_source_sha256"):
            raise ValueError("packet/control source missing")
        elapsed = row.get("elapsed_s")
        if not isinstance(elapsed, (int, float)) or (previous_time is not None and elapsed <= previous_time):
            raise ValueError("original time continuity missing")
        previous_time = elapsed
        if row.get("passenger_event") and not row.get("passenger_event_source_sha256"):
            raise ValueError("passenger event source missing")
    return {"case_id": case_id, "original_history_sha256": digest, "frame_count": 900,
            "first_original_frame": first, "last_original_frame": first + 899,
            "zone_source_sha256": expected_zone_sha256,
            "regulations_source_sha256": expected_regulations_sha256,
            "physical_visibility_verified": False, "legal_judgment": None}
