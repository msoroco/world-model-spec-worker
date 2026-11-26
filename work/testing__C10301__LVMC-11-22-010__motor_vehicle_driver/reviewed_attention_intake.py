"""Validate original sources before authoring an interior-attention sweep.

This checks provenance and physical sweep feasibility. It does not decide the
legal meaning of full time and attention or expand a sweep on its own.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


ASSIGNMENT = "testing__C10301__LVMC-11-22-010__motor_vehicle_driver"
LAW = "LVMC-11-22-010"
REQUIRED_SOURCES = ("municipal_jurisdiction", "original_site", "interior_sensor", "control_feasibility")


def _finite(value: object, name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(name + " must be a finite number")
    return float(value)


def _source(packet: dict, key: str, root: Path) -> dict:
    entry = packet.get("sources", {}).get(key)
    if not isinstance(entry, dict) or entry.get("review_status") != "reviewed":
        raise ValueError("reviewed source required: " + key)
    path = Path(entry.get("path", ""))
    if not path.is_absolute():
        path = root / path
    if not path.is_file() or path.is_symlink():
        raise ValueError("source file missing or symlinked: " + key)
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != entry.get("sha256"):
        raise ValueError("source hash mismatch: " + key)
    if not isinstance(entry.get("citation"), str) or not entry["citation"].strip():
        raise ValueError("source citation required: " + key)
    return {"path": str(path.resolve()), "sha256": actual, "citation": entry["citation"]}


def validate(packet_path: Path, *, allow_diagnostic: bool = False) -> dict:
    packet_path = Path(packet_path)
    if not packet_path.is_file() or packet_path.is_symlink():
        raise ValueError("reviewed attention packet missing or symlinked")
    raw = packet_path.read_bytes()
    packet = json.loads(raw)
    if packet.get("format") != "worker-reviewed-attention-sweep" or packet.get("assignment_id") != ASSIGNMENT or packet.get("law_id") != LAW:
        raise ValueError("attention packet identity mismatch")
    if packet.get("diagnostic_fixture") is not False and not allow_diagnostic:
        raise ValueError("diagnostic attention packet cannot authorize a sweep")
    sources = {key: _source(packet, key, packet_path.parent) for key in REQUIRED_SOURCES}
    axis = packet.get("axis", {})
    if axis.get("variable") != "interior_distraction_target_s" or axis.get("observable") != "original_eyes_off_road_duration_s" or axis.get("unit") != "s":
        raise ValueError("source-bound interior attention axis required")
    minimum = _finite(axis.get("min"), "axis minimum")
    maximum = _finite(axis.get("max"), "axis maximum")
    spacing = _finite(axis.get("spacing"), "axis spacing")
    if minimum < 0 or maximum > 45 or maximum <= minimum or spacing <= 0 or maximum - minimum < 2 * spacing:
        raise ValueError("physical axis needs at least three feasible levels")
    if abs(round((maximum - minimum) / spacing) * spacing - (maximum - minimum)) > 1e-6:
        raise ValueError("physical axis endpoints must align with spacing")
    feasibility = json.loads(Path(sources["control_feasibility"]["path"]).read_text())
    if feasibility.get("format") != "reviewed-attention-control-feasibility" or feasibility.get("native_verified") is not True:
        raise ValueError("original control feasibility readback required")
    if any(_finite(feasibility.get(k), "feasibility " + k) != v for k, v in
           (("minimum_s", minimum), ("maximum_s", maximum), ("resolution_s", spacing))):
        raise ValueError("axis differs from reviewed physical feasibility")
    sensor = json.loads(Path(sources["interior_sensor"]["path"]).read_text())
    if sensor.get("format") != "reviewed-original-interior-sensor" or sensor.get("native_verified") is not True:
        raise ValueError("original interior sensor readback required")
    if sensor.get("observable") != axis["observable"] or not sensor.get("sensor_id"):
        raise ValueError("interior sensor cannot measure selected observable")
    if sensor.get("frame_join") != "original_native_frame" or sensor.get("sampling_rate_hz") != 20:
        raise ValueError("20 Hz original-frame interior join required")
    measurement = axis.get("measurement", {})
    if measurement.get("method") != "original interior sensor cumulative duration history" or measurement.get("statistic") != "max" or measurement.get("time_window") != "full original 45-second alley operation":
        raise ValueError("interior measurement contract missing")
    if not axis.get("range_rationale") or not axis.get("spacing_rationale"):
        raise ValueError("physical range and spacing rationale required")
    return {"format": "worker-reviewed-attention-intake", "assignment_id": ASSIGNMENT,
            "packet_sha256": hashlib.sha256(raw).hexdigest(), "source_sha256": {k: v["sha256"] for k, v in sources.items()},
            "axis": axis, "sensor_id": sensor["sensor_id"],
            "legal_judgment": "unresolved", "diagnostic_fixture": packet.get("diagnostic_fixture") is not False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("attention intake output already exists")
    result = validate(args.packet)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
