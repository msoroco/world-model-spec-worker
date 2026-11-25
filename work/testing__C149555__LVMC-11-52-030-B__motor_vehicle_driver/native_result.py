"""Write a canonical Native result from sealed freight source measurements."""

from __future__ import annotations

import hashlib
from pathlib import Path

from freight_contract import SourceError, VARIANTS, audit_source_bundle, require_case_completion


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_native_result(attempt: Path, manifest: dict, *, writer=None) -> Path:
    attempt = Path(attempt).resolve(strict=True)
    case_id = manifest["case_id"]
    variant = case_id.rsplit("__", 1)[-1]
    measured = audit_source_bundle(manifest, case_id=case_id, variant=variant,
                                   source_root=attempt, require_raw=True)
    completion = require_case_completion(measured)
    if writer is None:
        from scenario_pipeline.worker_exchange.native_output import write_result
        writer = write_result
    videos = [name + ".mkv" for name in
              ("overview", "approach", "reference_corner", "driver_reference")]
    videos.append("raw.mkv")
    for video in videos:
        if not (attempt / video).is_file():
            raise SourceError("missing retained original video: " + video)
    packet = manifest["sources"]["native_result"]
    source_hashes = {name: ref["sha256"] for name, ref in manifest["sources"].items()}
    source_hashes.update({"raw_" + name: ref["sha256"] for name, ref in
                          manifest["raw_sources"].items()})
    target_checks = []
    targets = {
        "freight_activity": (VARIANTS[variant]["activity"], measured["observed_action"]),
        "commercial_status": (VARIANTS[variant]["commercial"], measured["commercial_status_reviewed"]),
        "stop_inside_yellow_zone": (VARIANTS[variant]["in_zone"], measured["stopped_inside_zone"]),
        "inside_posted_window": (VARIANTS[variant]["in_window"], measured["inside_posted_window"]),
    }
    for target, (requested, value) in targets.items():
        target_checks.append({"target": target, "requested": requested,
                              "measured": value, "method": "sealed original source audit",
                              "tolerance": 0, "matched": value == requested,
                              "physical_cause_confirmed": target in {"freight_activity", "stop_inside_yellow_zone"},
                              "cause_evidence": packet["path"]})
    result = {
        "case_id": case_id,
        "measured_values": measured,
        "target_checks": target_checks,
        "setup_confirmed": True,
        "behavior_attempted": True,
        "maneuver_completed": completion["physical_completion"],
        "termination_reason": "900 original Native frames captured; physical target measured",
        "physical_failure_flags": {"source_integrity": False,
                                   "motion_incomplete": False,
                                   "legal_purpose_unresolved": True},
        "trace_reference": "trace.jsonl",
        "video_references": videos,
        "video_frame_map_reference": "frame-map.jsonl",
        "recording_description": "Commercial freight vehicle approaches and halts at a sourced yellow curb; cargo motion, posted time and stopped footprint are measured from original frames.",
        "recording_evidence": [{"path": ref["path"], "sha256": ref["sha256"]}
                               for ref in manifest["sources"].values()],
        "realized_observables": {"original_frames": 900,
                                 "final_halt_duration_s": measured["final_halt_duration_s"],
                                 "observed_freight_action": measured["observed_action"],
                                 "source_hashes": source_hashes},
        "physical_checks": {"setup": {"status": "met"},
                            "maneuver": {"status": "met"}},
        "diagnostic_fixture": False,
        "physical_acceptance_claimed": False,
        "legal_conclusion": "unresolved",
    }
    # Native format prohibits a legal verdict, but permits an explicit unresolved
    # note. The independent delivery audit must still review actual pixels.
    return writer(attempt, result)
