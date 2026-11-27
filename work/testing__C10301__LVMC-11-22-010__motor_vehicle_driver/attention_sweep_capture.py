"""Source-gated original interior stream for a future attention sweep case.

The request is a control target. Only the Native sensor readback is a measured
observation; neither is a finding about statutory attention.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from interior_attention import measure, request_control, sample
from reviewed_attention_intake import validate


class AttentionSweepCapture:
    def __init__(self, packet_path: Path, case_id: str, target_s: float,
                 *, allow_diagnostic: bool = False):
        intake = validate(packet_path, allow_diagnostic=allow_diagnostic)
        axis = intake["axis"]
        low, high, spacing = (axis[key] for key in ("min", "max", "spacing"))
        if (type(target_s) not in (int, float) or not low <= target_s <= high
                or abs(round((target_s - low) / spacing) * spacing + low - target_s) > 1e-6):
            raise ValueError("attention target outside reviewed physical sweep grid")
        if not isinstance(case_id, str) or not case_id.startswith(intake["assignment_id"] + "__"):
            raise ValueError("attention sweep case identity differs")
        self.intake = intake
        self.case_id = case_id
        self.target_s = float(target_s)
        self.sensor = {
            "review_status": "reviewed",
            "observable": axis["observable"],
            "sensor_id": intake["sensor_id"],
            "source_sha256": intake["source_sha256"]["interior_sensor"],
        }
        self.controls = []
        self.samples = []

    def request(self, adapter, actor, frame_index: int) -> dict:
        if frame_index != len(self.controls) or len(self.samples) != frame_index:
            raise ValueError("attention control must precede the corresponding Native tick")
        row = request_control(adapter, actor, self.case_id, frame_index,
                              self.target_s, self.sensor)
        self.controls.append(row)
        return row

    def read(self, adapter, actor, snapshot) -> dict:
        index = len(self.samples)
        if len(self.controls) != index + 1:
            raise ValueError("original attention control readback required before sensor read")
        row = sample(adapter, actor, snapshot, self.case_id, self.sensor)
        if index and (row["native_frame"] != self.samples[-1]["native_frame"] + 1
                      or abs(row["native_time_s"] - self.samples[-1]["native_time_s"] - .05) > .001):
            raise ValueError("original interior Native frame continuity failed")
        self.samples.append(row)
        return row

    def finish(self, output: Path, *, expected_frames: int = 900) -> dict:
        if len(self.controls) != expected_frames or len(self.samples) != expected_frames:
            raise ValueError("complete original interior control and sensor streams required")
        output = Path(output)
        if not output.is_dir() or any((output / name).exists() for name in
                                      ("interior-control.jsonl", "interior-original.jsonl")):
            raise ValueError("fresh interior output directory required")
        control = output / "interior-control.jsonl"
        original = output / "interior-original.jsonl"
        for path, rows in ((control, self.controls), (original, self.samples)):
            path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
        measured = measure(original, self.case_id, expected_frames=expected_frames)
        return {
            "format": "worker-original-interior-capture",
            "case_id": self.case_id,
            "requested_target_s": self.target_s,
            "measured": measured,
            "control_source_sha256": hashlib.sha256(control.read_bytes()).hexdigest(),
            "intake_packet_sha256": self.intake["packet_sha256"],
            "diagnostic_fixture": self.intake["diagnostic_fixture"],
            "legal_judgment": "unresolved",
            "physical_acceptance_claimed": False,
        }
