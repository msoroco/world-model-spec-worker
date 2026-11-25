"""Independent saved-source audit for the three NRS 484B.287(1)(c) cases.

This audits measurements and source bindings. It never makes a legal finding;
the statutory adjacency, official status, and 484B.290 exception require
independent review of the original sources.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from native_observation import CAMERAS
from saved_camera_audit import audit_saved
from site_geometry import assess_site

PREFIX = "testing__C111329__NRS-484B-287-1c__pedestrian__"
CASES = {
    PREFIX + "midblock_unmarked_operating": (False, True),
    PREFIX + "midblock_marked_operating": (True, True),
    PREFIX + "midblock_unmarked_inactive": (False, False),
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _native_provenance(provenance: dict, receipt: dict, case_id: str) -> dict:
    """Bind the original observation to a separately sealed Native attempt."""
    if not isinstance(provenance, dict) or provenance.get("kind") != "original_native":
        raise ValueError("sealed original Native provenance required")
    if provenance.get("case_id") != case_id or provenance.get("observation_sha256") != receipt["sha256"]:
        raise ValueError("Native provenance exact case or observation mismatch")
    if provenance.get("diagnostic_fixture") is not False:
        raise ValueError("diagnostic fixture cannot establish Native provenance")
    seal = Path(provenance.get("seal_path", "")).resolve()
    observation = Path(receipt["path"]).resolve()
    if not seal.is_file() or seal.parent != observation.parent or _sha(seal) != provenance.get("seal_sha256"):
        raise ValueError("Native seal source hash mismatch")
    document = json.loads(seal.read_text())
    if document.get("case_id") != case_id or document.get("observation_sha256") != receipt["sha256"] or document.get("frame_count") != receipt["frame_count"]:
        raise ValueError("Native seal observation binding mismatch")
    if document.get("restored") is not True or document.get("errors") != []:
        raise ValueError("Native restoration or acquisition failure")
    return {"seal_path": str(seal), "seal_sha256": provenance["seal_sha256"]}


def audit_delivery(packet: dict, receipt: dict, *, case_id: str,
                   native_provenance: dict | None = None,
                   required_frames: int = 900, camera_dimensions=None,
                   diagnostic_fixture: bool = False) -> dict:
    """Decode all four original cameras and verify the exact case distinction."""
    if case_id not in CASES:
        raise ValueError("unknown exact NRS 484B.287(1)(c) case")
    expected_marked, expected_operation = CASES[case_id]
    site = assess_site(packet, require_operating=False)
    if site["marked_crosswalk_present"] is not expected_marked:
        raise ValueError("exact case marked-crosswalk source mismatch")
    media = audit_saved(packet, receipt, expected_case_id=case_id,
                        required_frames=required_frames,
                        camera_dimensions=camera_dimensions)
    motion = media["motion"]
    if motion["both_devices_operating_during_crossing"] is not expected_operation:
        raise ValueError("exact case original device-operation mismatch")
    if not motion["crossed_both_highway_banks"]:
        raise ValueError("original highway crossing incomplete")
    if diagnostic_fixture:
        if native_provenance is not None:
            raise ValueError("diagnostic fixture cannot carry Native provenance")
        native = None
    else:
        native = _native_provenance(native_provenance, receipt, case_id)
    return {
        "format": "worker-pedestrian-delivery-audit",
        "case_id": case_id,
        "source_observation_sha256": receipt["sha256"],
        "source_sha256": site["source_sha256"],
        "frame_count": media["frame_count"],
        "full_pixel_decodes": media["decoded_images"],
        "camera_source_sha256": media["camera_source_sha256"],
        "camera_names": list(CAMERAS),
        "marked_crosswalk_observed": expected_marked,
        "both_devices_operating_during_crossing": expected_operation,
        "crossing_frame_range": motion["observed_crossing_frame_range"],
        "native_provenance": native,
        "diagnostic_fixture": diagnostic_fixture,
        "physical_acceptance": False,
        "legal_adjacency": "undetermined",
        "legal_official_status": "undetermined",
        "nrs_484b_290_exception": "undetermined",
        "legal_verdict": None,
    }
