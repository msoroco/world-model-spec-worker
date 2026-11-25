"""Independent saved-source acceptance audit for one exact roundabout attempt."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from capture_roundabout import CAMERAS
from roundabout_measurements import ASSIGNMENT_ID, SUFFIXES
from saved_roundabout_camera_audit import audit_saved


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_delivery(*, case_id, map_path, trace_path, receipt_path,
                   camera_dimensions=None):
    if case_id not in {ASSIGNMENT_ID + "__" + suffix for suffix in SUFFIXES}:
        raise ValueError("unknown exact delivery case")
    source = json.loads(Path(map_path).read_text())
    if source.get("case_id") != case_id:
        raise ValueError("exact construction case mismatch")
    cameras = audit_saved(case_id=case_id, map_path=map_path,
                          trace_path=trace_path, receipt_path=receipt_path,
                          camera_dimensions=camera_dimensions)
    motion = cameras["motion"]
    receipt = json.loads(Path(receipt_path).read_text())
    if receipt.get("diagnostic_fixture") or receipt.get("frame_count") != 900:
        raise ValueError("full original 900-frame attempt required")
    if motion["source_bindings"]["map_packet_sha256"] != _sha(map_path) or (
            motion["source_bindings"]["original_trace_sha256"] != _sha(trace_path)):
        raise ValueError("saved motion source bindings differ")
    if set(cameras["camera_source_sha256"]) != set(CAMERAS):
        raise ValueError("four original camera sources required")
    return {"format": "worker-roundabout-delivery-audit",
            "case_id": case_id, "source": {"map_sha256": _sha(map_path),
                "trace_sha256": _sha(trace_path), "receipt_sha256": _sha(receipt_path),
                "camera_sha256": cameras["camera_source_sha256"]},
            "frame_count": 900, "decoded_images": 3600,
            "ego_entry_lane_id": motion["ego_entry_lane_id"],
            "connected_circulating_lane_id": motion["connected_circulating_lane_id"],
            "opponent_circulating_lane_id": motion["opponent_circulating_lane_id"],
            "first_observed_ego_entry_frame": motion["first_observed_ego_entry_frame"],
            "opponent_in_ring_at_ego_entry": motion["opponent_in_ring_at_ego_entry"],
            "opponent_in_conflict_at_ego_entry": motion["opponent_in_conflict_at_ego_entry"],
            "body_separation_at_entry_m": motion["body_separation_at_entry_m"],
            "minimum_sampled_body_separation_m": motion["minimum_sampled_body_separation_m"],
            "legal_gap_judgment": "unresolved", "physical_acceptance": False,
            "legal_verdict": None}
