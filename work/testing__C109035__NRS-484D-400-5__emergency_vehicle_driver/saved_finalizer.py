"""Saved-only measurement for exact C109035 warning-device cases.

The receipt is observational. It never decides authorization, warning intent,
500-foot audibility, recipient hearing, or statutory compliance.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from emergency_scene import CASE_KNOBS
from warning_audit import audit


PREFIX = "testing__C109035__NRS-484D-400-5__emergency_vehicle_driver__"
SOURCES = {"site_packet", "device_trace", "camera_trace", "actor_trace",
           "dispatch_context", "equipment_record"}


def _read(folder: Path, reference: dict) -> bytes:
    relative = reference.get("path")
    if (not isinstance(relative, str) or not relative or
            Path(relative).is_absolute() or
            any(part in ("", ".", "..") for part in relative.split("/")) or
            "\\" in relative):
        raise ValueError("Original source path invalid")
    base = folder.resolve(strict=True)
    target = base
    for part in Path(relative).parts:
        target = target / part
        if target.is_symlink():
            raise ValueError("Original source absent or symlinked")
    if not target.is_file() or not target.resolve(strict=True).is_relative_to(base):
        raise ValueError("Original source absent or symlinked")
    data = target.read_bytes()
    if hashlib.sha256(data).hexdigest() != reference.get("sha256"):
        raise ValueError("Original source hash mismatch")
    return data


def finalize(folder: Path, *, case_id: str) -> dict:
    """Reopen originals and measure case-specific temporal/device conditions."""
    folder = Path(folder)
    if not case_id.startswith(PREFIX) or case_id[len(PREFIX):] not in CASE_KNOBS:
        raise ValueError("Unknown exact case")
    receipt_file = folder / "capture_receipt.json"
    if receipt_file.is_symlink():
        raise ValueError("Capture receipt symlinked")
    receipt_bytes = receipt_file.read_bytes()
    receipt = json.loads(receipt_bytes)
    if receipt.get("case_id") != case_id or receipt.get("source_kind") != "original_capture":
        raise ValueError("Original capture case identity mismatch")
    if receipt.get("physical_acceptance_claimed") is not False:
        raise ValueError("Original capture receipt claims physical acceptance")
    source_keys = set(receipt.get("sources", {}))
    if source_keys not in (SOURCES, SOURCES | {"device_samples"}) or not receipt.get("site_packet_sha256"):
        raise ValueError("Original capture source inventory incomplete")
    originals = {key: _read(folder, ref) for key, ref in receipt["sources"].items()}
    if hashlib.sha256(originals["site_packet"]).hexdigest() != receipt["site_packet_sha256"]:
        raise ValueError("Reviewed original site source differs")
    site = json.loads(originals["site_packet"])
    if site.get("case_id") != case_id or not site.get("reviewer") or not site.get("source_citation"):
        raise ValueError("Original reviewed site identity missing")
    dispatch = json.loads(originals["dispatch_context"])
    equipment = json.loads(originals["equipment_record"])
    for kind, document in (("dispatch_context", dispatch), ("equipment_record", equipment)):
        if document.get("case_id") != case_id or document.get("source_kind") != kind:
            raise ValueError("Independent source case identity mismatch: " + kind)
        if not document.get("reviewer") or not document.get("source_citation"):
            raise ValueError("Independent source review missing: " + kind)
    knobs = CASE_KNOBS[case_id[len(PREFIX):]]
    if dispatch.get("event") != knobs["event"]:
        raise ValueError("Documented event differs from exact construction")
    interval = dispatch.get("event_interval_frames")
    if (not isinstance(interval, list) or len(interval) != 2 or
            any(type(value) is not int for value in interval) or
            not 0 <= interval[0] <= interval[1] < 900):
        raise ValueError("Documented event interval invalid")
    rows = [json.loads(line) for line in originals["device_trace"].splitlines()]
    cameras = [json.loads(line) for line in originals["camera_trace"].splitlines()]
    actors = [json.loads(line) for line in originals["actor_trace"].splitlines()]
    samples = ([json.loads(line) for line in originals["device_samples"].splitlines()]
               if "device_samples" in originals else None)
    if len(rows) != 900 or len(cameras) != 900 or len(actors) != 900:
        raise ValueError("Original frame count incomplete")
    if samples is not None and len(samples) != 900:
        raise ValueError("Independent device sample count incomplete")
    if samples is not None and (any(not isinstance(sample, dict) or
                                    not isinstance(sample.get("sample_id"), str) or
                                    not sample["sample_id"] for sample in samples) or
                                len({sample["sample_id"] for sample in samples}) != 900):
        raise ValueError("Independent device sample identity missing or reused")
    first_native = receipt.get("native_first_frame")
    if type(first_native) is not int or receipt.get("native_last_frame") != first_native + 899:
        raise ValueError("Original native frame bounds invalid")
    actor_ids = None
    for tick, (row, camera, actor_row) in enumerate(zip(rows, cameras, actors)):
        if row.get("frame") != tick or row.get("native_frame") != first_native + tick:
            raise ValueError("Original native device frame gap")
        if camera.get("frame") != tick or camera.get("native_frame") != first_native + tick:
            raise ValueError("Original native camera frame gap")
        if (actor_row.get("frame") != tick or
                actor_row.get("native_frame") != first_native + tick):
            raise ValueError("Original native actor frame gap")
        ids = []
        for role in ("ego", "pedestrian"):
            actor = actor_row.get(role, {})
            if actor.get("role") != role or type(actor.get("actor_id")) is not int:
                raise ValueError("Original actor identity missing")
            ids.append(actor["actor_id"])
            if any(type(actor.get(key)) not in (int, float) or
                   not math.isfinite(actor[key]) for key in (
                       "x_m", "y_m", "z_m", "roll_deg", "pitch_deg", "yaw_deg")):
                raise ValueError("Original actor pose invalid")
        if ids[0] == ids[1] or (actor_ids is not None and ids != actor_ids):
            raise ValueError("Original actor identity changed")
        actor_ids = ids
        if any(type(row.get(key)) is not bool for key in (
                "siren_commanded", "warning_lamp_commanded", "siren_active", "warning_lamp_active")):
            raise ValueError("Original command or device readback missing")
        if row.get("device_source_type") in (None, "", "command_echo") or not row.get("device_source_citation"):
            raise ValueError("Independent device readback source missing")
        if samples is not None:
            sample = samples[tick]
            if (sample.get("native_frame") != row["native_frame"] or
                    sample.get("siren_active") != row["siren_active"] or
                    sample.get("warning_lamp_active") != row["warning_lamp_active"] or
                    sample.get("source_type") != row["device_source_type"] or
                    sample.get("source_citation") != row["device_source_citation"]):
                raise ValueError("Independent device sample and trace mismatch")
        if set(camera.get("sources", {})) != {"overview", "approach", "reference_corner", "driver_reference"} or not all(camera["sources"].values()):
            raise ValueError("Four original camera references missing")
    observed = audit(folder, receipt)
    commanded_siren = sum(row["siren_commanded"] for row in rows)
    commanded_lamps = sum(row["warning_lamp_commanded"] for row in rows)
    if bool(commanded_siren) != knobs["siren"] or bool(commanded_lamps) != knobs["lamps"]:
        raise ValueError("Recorded command differs from exact construction")
    return {
        "case_id": case_id,
        "capture_receipt_sha256": hashlib.sha256(receipt_bytes).hexdigest(),
        "source_sha256": {key: ref["sha256"] for key, ref in receipt["sources"].items()},
        "native_frame_count": 900,
        "commanded_siren_frames": commanded_siren,
        "commanded_warning_lamp_frames": commanded_lamps,
        "observed": observed,
        "original_actor_ids": {"ego": actor_ids[0], "pedestrian": actor_ids[1]},
        "original_actor_start": actors[0],
        "original_actor_end": actors[-1],
        "physical_completion": "unverified",
        "actual_camera_pixels": "unverified",
        "legal_conclusion": None,
    }
