"""Run one source-reviewed exact elevator case with owner cleanup.

The adapter supplies the Native fixture, vehicle, controller, original ticks and
readbacks. A CPU fake can test call flow but cannot establish physical success.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from native_history_capture import capture_original_history
from parking import CASES, build_case
from reviewed_site import verify


def run_case(adapter, packet_path: Path, source_root: Path, case_id: str,
             body_length_m: float, output: Path) -> dict:
    packet = verify(packet_path, source_root)
    expected_prefix = packet["assignment_id"] + "__"
    if not case_id.startswith(expected_prefix):
        raise ValueError("exact assignment case mismatch")
    local_id = case_id[len(expected_prefix):]
    case = next((item for item in CASES if item.id == local_id), None)
    if case is None:
        raise ValueError("unknown exact sidewalk-elevator case")
    site = dict(packet["site"])
    site["site_sha256"] = hashlib.sha256(Path(packet_path).read_bytes()).hexdigest()
    built = build_case(adapter, site, case, body_length_m)
    try:
        result = capture_original_history(adapter, site, case, output)
        result["case_id"] = case_id
        result["site_packet_sha256"] = site["site_sha256"]
        return result
    finally:
        for actor in reversed(built["owned"]):
            adapter.destroy(actor)
