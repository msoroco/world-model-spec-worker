"""Original instrument-log adapter for the emergency Native capture.

The log is supplied by an independent device instrument. This module binds its
unaltered JSONL bytes to one exact case and Native frame sequence; it cannot
measure 500-foot audibility or replace a reviewed instrument source.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from camera_recorder import CameraRecorder, PROFILE_SIZES
from device_readback import DeviceReadback
from native_capture import FRAMES, PREFIX, capture


class OriginalInstrumentLog:
    def __init__(self, path: Path, *, case_id: str, expected_sha256: str,
                 source_type: str, source_citation: str):
        if not case_id.startswith(PREFIX):
            raise ValueError("Exact emergency case required")
        raw = Path(path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise ValueError("Original instrument log hash mismatch")
        lines = raw.splitlines(keepends=True)
        if len(lines) != FRAMES or not raw.endswith(b"\n") or any(
                not line.endswith(b"\n") or line.endswith(b"\r\n") for line in lines):
            raise ValueError("Original instrument log must contain 900 complete frames")
        rows = []
        for line in lines:
            try:
                row = json.loads(line)
            except (ValueError, UnicodeDecodeError) as exc:
                raise ValueError("Original instrument sample JSON invalid") from exc
            if not isinstance(row, dict) or row.get("case_id") != case_id:
                raise ValueError("Original instrument sample case mismatch")
            if row.get("source_type") != source_type or row.get("source_citation") != source_citation:
                raise ValueError("Original instrument sample source mismatch")
            if any(type(row.get(key)) is not bool for key in ("siren_active", "warning_lamp_active")):
                raise ValueError("Original instrument device state missing")
            if any(key in row for key in ("siren_commanded", "warning_lamp_commanded")):
                raise ValueError("Original instrument contains command echo fields")
            rows.append(row)
        frames = [row.get("native_frame") for row in rows]
        if any(type(frame) is not int for frame in frames) or any(
                current != previous + 1 for previous, current in zip(frames, frames[1:])):
            raise ValueError("Original instrument frame sequence invalid")
        if any(not isinstance(row.get("sample_id"), str) or not row["sample_id"] for row in rows):
            raise ValueError("Original instrument sample ID missing")
        if len({row["sample_id"] for row in rows}) != FRAMES:
            raise ValueError("Original instrument sample IDs reused")
        self.case_id = case_id
        self.source_sha256 = expected_sha256
        self.first_frame = frames[0]
        self.samples = dict(zip(frames, lines))

    def sample(self, ego, native_frame: int) -> bytes:
        try:
            return self.samples[native_frame]
        except KeyError as exc:
            raise ValueError("Original instrument sample missing for Native frame") from exc


def capture_with_original_adapters(world, carla_api, *, case_id: str,
                                   site_packet: Path, dispatch_document: Path,
                                   equipment_document: Path, instrument_log: Path,
                                   instrument_sha256: str, instrument_source_type: str,
                                   instrument_source_citation: str, output: Path,
                                   device_command, drive_step, camera_frame_reader,
                                   camera_source_ids: dict, camera_sizes: dict | None = None,
                                   diagnostic: bool = False, camera_binding=None):
    """Connect the original instrument and four camera sources to Native capture.

    camera_frame_reader must return four original CARLA Image objects for the
    requested world frame. A caller may use reduced sizes only in diagnostic
    tests; production uses the pinned CameraRecorder profile.
    """
    if not diagnostic and camera_sizes is not None and camera_sizes != PROFILE_SIZES:
        raise ValueError("Production camera dimensions must match pinned profile")
    instrument = OriginalInstrumentLog(
        instrument_log, case_id=case_id, expected_sha256=instrument_sha256,
        source_type=instrument_source_type,
        source_citation=instrument_source_citation)
    readback = DeviceReadback(
        instrument.sample, source_type=instrument_source_type,
        source_citation=instrument_source_citation)
    recorder = CameraRecorder(output, camera_frame_reader, case_id=case_id,
                              source_ids=camera_source_ids, sizes=camera_sizes,
                              binding=camera_binding)
    receipt = capture(
        world, carla_api, case_id=case_id, site_packet=site_packet,
        dispatch_document=dispatch_document,
        equipment_document=equipment_document, output=output,
        device_command=device_command, device_readback=readback,
        drive_step=drive_step, camera_capture=recorder)
    if receipt["native_first_frame"] != instrument.first_frame:
        raise ValueError("Original instrument and Native first frame mismatch")
    return receipt
