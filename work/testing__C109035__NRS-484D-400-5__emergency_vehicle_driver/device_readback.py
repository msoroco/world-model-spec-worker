"""Frame-joined independent warning-device observations for Native capture.

The caller supplies an instrument reader. Its returned JSON bytes are retained
unaltered; this adapter cannot establish acoustic range or pedestrian hearing.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


class DeviceReadback:
    def __init__(self, sample_reader, *, source_type: str, source_citation: str):
        if source_type not in {"instrument_telemetry", "acoustic_monitor", "external_device_log"}:
            raise ValueError("Independent device instrument source type required")
        if not source_citation:
            raise ValueError("Independent device source citation required")
        self.sample_reader = sample_reader
        self.source_type = source_type
        self.source_citation = source_citation
        self.samples = []
        self.sample_ids = set()
        self.last_frame = None

    def for_frame(self, ego, native_frame: int) -> dict:
        if type(native_frame) is not int or native_frame < 0:
            raise ValueError("Native device frame invalid")
        if self.last_frame is not None and native_frame != self.last_frame + 1:
            raise ValueError("Independent device sample frame gap")
        original = self.sample_reader(ego, native_frame)
        if not isinstance(original, bytes):
            raise ValueError("Independent device sample must be original JSON bytes")
        try:
            sample = json.loads(original)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError("Independent device sample JSON invalid") from exc
        if not isinstance(sample, dict) or sample.get("native_frame") != native_frame:
            raise ValueError("Independent device sample frame mismatch")
        sample_id = sample.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id or sample_id in self.sample_ids:
            raise ValueError("Independent device sample identity missing or reused")
        if any(type(sample.get(key)) is not bool for key in ("siren_active", "warning_lamp_active")):
            raise ValueError("Independent device state missing")
        if any(key in sample for key in ("siren_commanded", "warning_lamp_commanded")):
            raise ValueError("Command fields cannot serve as independent readback")
        if sample.get("source_type") != self.source_type or sample.get("source_citation") != self.source_citation:
            raise ValueError("Independent device sample source mismatch")
        self.samples.append(original)
        self.sample_ids.add(sample_id)
        self.last_frame = native_frame
        return {"siren_active": sample["siren_active"],
                "warning_lamp_active": sample["warning_lamp_active"],
                "source_type": self.source_type,
                "source_citation": self.source_citation}

    def seal(self, output: Path, first_frame: int, last_frame: int) -> dict:
        if not self.samples or len(self.samples) != last_frame - first_frame + 1 or self.last_frame != last_frame:
            raise ValueError("Independent device sample count incomplete")
        path = Path(output) / "device_samples.jsonl"
        if path.exists() or path.is_symlink():
            raise ValueError("Original device samples already exist")
        data = b"".join(sample.rstrip(b"\r\n") + b"\n" for sample in self.samples)
        path.write_bytes(data)
        return {"path": path.name, "sha256": hashlib.sha256(data).hexdigest()}
