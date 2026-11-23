"""Independent, source-bound audit of original emergency-device traces.

This reports observed relationships. It does not determine statutory compliance,
audibility at 500 feet, warning intent, or actual recipient hearing.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


EVENTS = {"emergency_call", "immediate_pursuit_actual", "immediate_pursuit_suspected", "none"}


def _load_source(folder: Path, relative: str, expected_sha: str) -> bytes:
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("Source path escapes capture")
    data = (folder / relative).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha:
        raise ValueError("Original source hash mismatch: " + relative)
    return data


def audit(folder: Path, source_manifest: dict) -> dict:
    if source_manifest.get("source_kind") != "original_capture":
        raise ValueError("Only original capture sources are auditable")
    refs = source_manifest.get("sources", {})
    required = {"device_trace", "dispatch_context", "equipment_record"}
    if not required.issubset(refs) or set(refs) - (required | {"camera_trace"}):
        raise ValueError("Required source inventory incomplete")
    documents = {}
    for key, ref in refs.items():
        documents[key] = _load_source(folder, ref["path"], ref["sha256"])
    context = json.loads(documents["dispatch_context"])
    equipment = json.loads(documents["equipment_record"])
    samples = [json.loads(line) for line in documents["device_trace"].decode().splitlines() if line]
    if context.get("event") not in EVENTS or context.get("source_status") != "documented":
        raise ValueError("Event source missing or undocumented")
    if equipment.get("authorization_source") is None or equipment.get("device_installation_source") is None:
        raise ValueError("Authorization or device inventory missing")
    if len(samples) != 900 or [x.get("frame") for x in samples] != list(range(900)):
        raise ValueError("Original 45-second 20-Hz frame sequence incomplete")
    if "camera_trace" in documents:
        camera_samples = [json.loads(line) for line in documents["camera_trace"].decode().splitlines() if line]
        if len(camera_samples) != 900 or [x.get("frame") for x in camera_samples] != list(range(900)):
            raise ValueError("Original camera frame sequence incomplete")
        for device, camera in zip(samples, camera_samples):
            if camera.get("native_frame") != device.get("native_frame") or set(camera.get("sources", {})) != {"front", "rear", "left", "right"}:
                raise ValueError("Original camera/source synchronization mismatch")
    for sample in samples:
        if not isinstance(sample.get("siren_active"), bool) or not isinstance(sample.get("warning_lamp_active"), bool):
            raise ValueError("Original device state missing")
        if abs(float(sample.get("elapsed_s", -1)) - sample["frame"] / 20) > 0.001:
            raise ValueError("Device trace timing mismatch")
    siren_frames = [x["frame"] for x in samples if x["siren_active"]]
    lamp_frames = [x["frame"] for x in samples if x["warning_lamp_active"]]
    event_start, event_end = context.get("event_interval_frames", [None, None])
    event_overlaps_siren = bool(siren_frames) and event_start is not None and all(event_start <= i <= event_end for i in siren_frames)
    return {
        "observed_siren_frames": len(siren_frames),
        "observed_warning_lamp_frames": len(lamp_frames),
        "event": context["event"],
        "all_siren_frames_within_documented_event": event_overlaps_siren,
        "lamp_without_siren_observed": bool(lamp_frames) and not siren_frames,
        "audibility_500ft_documentation_status": equipment.get("audibility_500ft_status", "unknown"),
        "recipient_hearing": "unknown",
        "warning_purpose": "requires_independent_review",
        "physical_status": "original_source_audit_only",
    }
