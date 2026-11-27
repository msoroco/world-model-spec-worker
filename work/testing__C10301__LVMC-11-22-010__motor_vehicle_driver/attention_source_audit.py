"""Independently reopen a saved original interior attention acquisition.

This checks source integrity and frame joins. It does not infer legal attention.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from reviewed_attention_intake import validate


def _read_rows(path: Path, expected: int) -> tuple[bytes, list[dict]]:
    if not path.is_file() or path.is_symlink():
        raise ValueError("original interior source missing or symlinked")
    raw = path.read_bytes()
    try:
        rows = [json.loads(line) for line in raw.splitlines()]
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("original interior source is not JSONL") from exc
    if len(rows) != expected or not all(isinstance(row, dict) for row in rows):
        raise ValueError("complete original interior source stream required")
    return raw, rows


def audit(directory: Path, packet_path: Path, capture_receipt: dict, *,
          allow_diagnostic: bool = False, expected_frames: int = 900) -> dict:
    intake = validate(packet_path, allow_diagnostic=allow_diagnostic)
    if capture_receipt.get("format") != "worker-original-interior-capture":
        raise ValueError("original interior capture receipt required")
    case_id = capture_receipt.get("case_id")
    if not isinstance(case_id, str) or not case_id.startswith(intake["assignment_id"] + "__"):
        raise ValueError("interior capture case identity differs")
    if capture_receipt.get("intake_packet_sha256") != intake["packet_sha256"]:
        raise ValueError("interior intake packet changed")
    if capture_receipt.get("diagnostic_fixture") != intake["diagnostic_fixture"]:
        raise ValueError("interior diagnostic provenance changed")
    if capture_receipt.get("legal_judgment") != "unresolved" or capture_receipt.get("physical_acceptance_claimed") is not False:
        raise ValueError("interior receipt makes unsupported acceptance claim")
    directory = Path(directory)
    control_raw, controls = _read_rows(directory / "interior-control.jsonl", expected_frames)
    sensor_raw, sensors = _read_rows(directory / "interior-original.jsonl", expected_frames)
    if hashlib.sha256(control_raw).hexdigest() != capture_receipt.get("control_source_sha256"):
        raise ValueError("original interior control source changed")
    measured = capture_receipt.get("measured", {})
    if hashlib.sha256(sensor_raw).hexdigest() != measured.get("source_sha256"):
        raise ValueError("original interior sensor source changed")
    sensor_sha = intake["source_sha256"]["interior_sensor"]
    if measured.get("sensor_source_sha256") != sensor_sha or measured.get("sensor_id") != intake["sensor_id"]:
        raise ValueError("reviewed interior sensor differs")
    target = capture_receipt.get("requested_target_s")
    axis = intake["axis"]
    low, high, spacing = (axis[key] for key in ("min", "max", "spacing"))
    if (type(target) not in (int, float) or not math.isfinite(target) or not low <= target <= high
            or abs(round((target - low) / spacing) * spacing + low - target) > 1e-6):
        raise ValueError("interior target differs from reviewed physical grid")
    expected_on = round(target * 20)
    first_frame = sensors[0].get("native_frame")
    first_time = sensors[0].get("native_time_s")
    if type(first_frame) is not int or type(first_time) not in (int, float) or not math.isfinite(first_time):
        raise ValueError("original interior source origin missing")
    for index, (control, sensor) in enumerate(zip(controls, sensors)):
        if (control.get("case_id") != case_id or control.get("frame_index") != index
                or control.get("requested_eyes_off_road") is not (index < expected_on)
                or control.get("control_source_sha256") != sensor_sha
                or control.get("native_verified") is not True
                or control.get("legal_judgment") != "unresolved"):
            raise ValueError("original interior control readback differs")
        if (sensor.get("source_kind") != "original_native_interior"
                or sensor.get("case_id") != case_id
                or sensor.get("native_frame") != first_frame + index
                or type(sensor.get("native_time_s")) not in (int, float)
                or not math.isfinite(sensor["native_time_s"])
                or abs(sensor["native_time_s"] - first_time - index / 20) > .001
                or sensor.get("sensor_id") != intake["sensor_id"]
                or sensor.get("sensor_source_sha256") != sensor_sha
                or type(sensor.get("eyes_off_road")) is not bool
                or sensor.get("native_verified") is not True):
            raise ValueError("original interior sensor frame join differs")
    duration = sum(row["eyes_off_road"] for row in sensors) / 20
    if (measured.get("case_id") != case_id or measured.get("original_frames") != expected_frames
            or measured.get("original_eyes_off_road_duration_s") != duration
            or measured.get("attention_state") != "unresolved"
            or measured.get("legal_judgment") != "unresolved"
            or measured.get("physical_acceptance_claimed") is not False):
        raise ValueError("saved interior measurement differs from original source")
    return {"format": "worker-original-interior-source-audit", "case_id": case_id,
            "original_frames": expected_frames, "control_source_sha256": hashlib.sha256(control_raw).hexdigest(),
            "sensor_source_sha256": hashlib.sha256(sensor_raw).hexdigest(),
            "intake_packet_sha256": intake["packet_sha256"],
            "requested_target_s": target, "measured_duration_s": duration,
            "diagnostic_fixture": intake["diagnostic_fixture"],
            "legal_judgment": "unresolved", "physical_acceptance_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--capture-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("interior audit output already exists")
    receipt = audit(args.directory, args.packet, json.loads(args.capture_receipt.read_text()))
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
