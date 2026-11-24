"""Publish the pinned Native result and immutable acquisition seal.

This module only closes a completed original capture. Physical visibility and
legal conclusions remain for independent review of the original pixels.
"""

import hashlib
import json
from pathlib import Path

from worker_exchange.native_output import seal_capture, write_result

from encode_original import VIEWS, audit_encoded
from parked_lamps import ASSIGNMENT, CASES, require


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def close(attempt, case_key, map_sha256, restoration):
    root = Path(attempt)
    require(case_key in CASES, "unknown exact case")
    require(restoration.get("restored") is True, "verified world restoration required")
    require(not (root / "result.json").exists() and not (root / "capture-seal.json").exists(),
            "retain previous Native closure")
    audited = audit_encoded(root, case_key, map_sha256)
    capture = root / "capture"
    packet = json.loads((capture / "capture-packet.json").read_text())
    require(packet["case_id"] == ASSIGNMENT + "__" + case_key and packet["frame_count"] == 900,
            "exact capture packet required")
    require(len((root / "trace.jsonl").read_text().splitlines()) == 900 and
            len((root / "video_frames.jsonl").read_text().splitlines()) == 900,
            "900 original trace and frame-map rows required")
    references = [VIEWS[name] + ".mkv" for name in VIEWS]
    target_checks = [{"target": "parked_vehicle_and_original_lamp_evidence",
                      "requested": CASES[case_key],
                      "measured": {"frame_count": 900, "native_first_frame": packet["native_first_frame"],
                                   "native_last_frame": packet["native_last_frame"],
                                   "lamp_visibility": "unreviewed", "revelation_at_1000_ft": "unreviewed"},
                      "method": "source-sealed Native readbacks and original four-view media",
                      "tolerance": {"time_join_s": 0.003, "speed_mps": 0.25},
                      "matched": None, "physical_cause_confirmed": False,
                      "cause_evidence": []}]
    result = {"measured_values": {"captured_frames": 900, "capture_fps": 20,
                                  "lamp_visibility": None, "revelation_at_1000_ft": None},
              "target_checks": target_checks, "setup_confirmed": True,
              "behavior_attempted": True, "maneuver_completed": True,
              "termination_reason": "planned_900_frame_parked_interval_completed",
              "physical_failure_flags": [],
              "trace_reference": "trace.jsonl",
              "video_references": references,
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": json.loads((root / "construction.json").read_text())["recording_description"],
              "recording_evidence": [
                  {"name": "parked_lamp_observations", "unit": "structured",
                   "reference": "parked_lamp_observations.jsonl"},
                  {"name": "reviewed_site_packet", "unit": "metadata",
                   "reference": "site_context.json"}],
              "realized_observables": {}}
    (root / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "native", "diagnostic_fixture": False,
        "case_id": packet["case_id"], "capture_packet_sha256": sha(capture / "capture-packet.json")
    }, sort_keys=True) + "\n")
    write_result(root, result)
    return seal_capture(root, frames=900, restoration=restoration, errors=[],
                        encoder_exit_codes={view: 0 for view in VIEWS.values()},
                        context={"map_sha256": map_sha256,
                                 "original_camera_identity": "capture/original_frame_map.json"})
