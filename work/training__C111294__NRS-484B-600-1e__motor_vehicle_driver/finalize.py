"""Saved-only C111294 measurement finalizer for unselected CPU fixtures."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from measure_speed import measure

INPUTS = ("native_samples.jsonl", "road.xodr")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _required(folder: Path, name: str) -> Path:
    path = folder / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def measure_subject_operation(rows: list[dict], speed: dict) -> dict:
    return {"ego_actor_id": speed["ego_actor_id"],
            "declared_blueprint": rows[0]["ego_blueprint"],
            "declared_role": rows[0]["ego_role"],
            "control_frames": sum(isinstance(r.get("ego_control"), dict) for r in rows),
            "personal_operation_legally_verified": False}


def measure_speed_relation(rows: list[dict], speed: dict) -> dict:
    return {"derived_peak_mph": speed["derived_peak_mph"],
            "uncertainty_mph": speed["uncertainty_mph"],
            "peak_interval_mph": speed["peak_interval_mph"],
            "statutory_value_mph": speed["statutory_value_mph"],
            "measured_relation": speed["measured_relation"],
            "velocity_source": speed["velocity_source"]}


def measure_unconditional_scope(rows: list[dict], road: ET.Element) -> dict:
    return {"authored_road_count": len(road.findall("road")),
            "authored_signal_count": len(road.findall(".//signal")),
            "measured_frames": len(rows),
            "posted_limit_used_in_speed_measurement": False,
            "territorial_applicability_verified": False}


def measure_other_vehicle_context(rows: list[dict], speed: dict) -> dict:
    return {"other_actor_id": speed["other_actor_id"],
            "other_declared_blueprint": rows[0]["other_blueprint"],
            "initial_native_position_m": rows[0]["other_position_m"],
            "last_native_position_m": rows[-1]["other_position_m"],
            "observed_route_motion_m": round(abs(
                rows[-1]["other_position_m"][1] - rows[0]["other_position_m"][1]), 6)}


def finalize(folder: Path, contract: dict, expected_source_sha256: str) -> dict:
    folder = Path(folder)
    paths = {name: _required(folder, name) for name in INPUTS}
    rows = [json.loads(line) for line in paths["native_samples.jsonl"].read_bytes().splitlines()]
    speed = measure(paths["native_samples.jsonl"], expected_source_sha256)
    road = ET.parse(paths["road.xodr"]).getroot()
    if road.tag != "OpenDRIVE" or len(road.findall("road")) != 6:
        raise ValueError("Saved map is not the six-road C111294 construction")
    values = {
        "subject_operation": measure_subject_operation(rows, speed),
        "speed_relation": measure_speed_relation(rows, speed),
        "unconditional_scope": measure_unconditional_scope(rows, road),
        "other_vehicle_context": measure_other_vehicle_context(rows, speed)}
    methods = {"subject_operation": "measure_subject_operation",
               "speed_relation": "measure_speed_relation",
               "unconditional_scope": "measure_unconditional_scope",
               "other_vehicle_context": "measure_other_vehicle_context"}
    report = {"case_id": contract["case_id"], "source_kind": speed["source_kind"],
              "source_complete": True, "selected": False, "accepted": False,
              "legal_verdict": None, "measurements": {}}
    for row in contract["requirements"]:
        key = row["output_key"]
        if key not in values or row["method"] != methods[key]:
            raise ValueError("Contract method differs from saved finalizer")
        report["measurements"][key] = {
            "method": methods[key], "value": values[key],
            "sources": {name: _sha(paths[name]) for name in row["inputs"]}}
    return report


def _rows(folder: Path, name: str) -> list[dict]:
    return [json.loads(line) for line in _required(folder, name).read_text().splitlines()
            if line.strip()]


def _body_xy(vertices: list) -> set[tuple[float, float]]:
    return {(round(v[0], 5), round(v[1], 5)) for v in vertices}


def verify_original_joins(folder: Path, expected: int = 480) -> dict:
    names = ("native_samples.jsonl", "trace.jsonl", "capture/evidence.jsonl",
             "video_frames.jsonl", "body_history.jsonl", "capture/native/frames.jsonl")
    native, trace, evidence, mapping, body, frames = (_rows(folder, name) for name in names)
    if any(len(source) != expected for source in
           (native, trace, evidence, mapping, body, frames)):
        raise ValueError("Original Native/Core frame counts differ")
    last_frame, last_time = -1, -1.0
    for index, (n, t, e, m, b, f) in enumerate(zip(native, trace, evidence, mapping, body, frames)):
        frame, time_s = m.get("native_frame"), m.get("time_s")
        if (type(frame) is not int or frame <= last_frame or
                not isinstance(time_s, (int, float)) or time_s <= last_time or
                m.get("video_frame") != index or m.get("carla_frame") != frame):
            raise ValueError("Original frame/time map differs")
        last_frame, last_time = frame, time_s
        if any(row != frame for row in (n.get("native_frame"), t.get("frame"),
                                        e.get("original_frame"), b.get("frame"), f.get("frame"))):
            raise ValueError("Original Native/Core frame identity differs")
        if any(abs(float(row) - time_s) > 1e-4 for row in
               (n.get("time_s"), t.get("time_s"), e.get("recording_time_s"),
                b.get("time_s"))):
            raise ValueError("Original Native/Core timestamp differs")
        native_body = _body_xy(n.get("ego_body_vertices_m", []))
        captured_body = _body_xy(e.get("ego", {}).get("body_vertices_m", []))
        history_body = _body_xy(b.get("body_vertices_m", []))
        if len(native_body) != 4 or native_body != captured_body or native_body != history_body:
            raise ValueError("Original Native/Core full body differs")
    manifest = json.loads(_required(folder, "capture/manifest.json").read_text())
    if manifest.get("frames") != expected or manifest.get("extraction_confirmed") is not True:
        raise ValueError("Original Core extraction incomplete")
    return {"frames": expected, "first_native_frame": mapping[0]["native_frame"],
            "last_native_frame": mapping[-1]["native_frame"],
            "source_hashes": {name: _sha(folder / name) for name in names}}


def _video_frames(path: Path) -> int:
    _required(path.parent, path.name)
    result = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
        "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    if result.returncode or not result.stdout.strip().isdigit():
        raise ValueError("Original source video decode failed: " + path.name)
    return int(result.stdout.strip())


def derive_recording_channels(folder: Path, config: dict) -> None:
    """Derive recording channels from retained Native rows, never fixture channels."""
    rows = _rows(folder, "native_samples.jsonl")
    declared = {item["name"] for item in config["recording_description"]["channels"]}
    expected = {"ego_pose", "ego_speed", "observed_speed", "other_vehicle_pose"}
    if declared != expected or len(rows) != 480:
        raise ValueError("Speed recording channel/source contract differs")
    values = {name: [] for name in expected}
    for row in rows:
        velocity = row["ego_velocity_mps"]
        speed = sum(component * component for component in velocity) ** 0.5
        current = {"ego_pose": row["ego_position_m"],
                   "ego_speed": speed, "observed_speed": speed / .44704,
                   "other_vehicle_pose": row["other_position_m"]}
        for name, value in current.items():
            values[name].append(json.dumps({"time_s": row["time_s"], "value": value,
                "source_kind": row["source_kind"]}, allow_nan=False) + "\n")
    channel_dir = folder / "channels"
    if channel_dir.exists():
        raise ValueError("Pre-existing derived channels are not accepted as saved source")
    channel_dir.mkdir()
    for name, lines in values.items():
        (channel_dir / (name + ".jsonl")).write_text("".join(lines))


def finalize_attempt(folder: Path, output: Path) -> dict:
    from worker_exchange.native_output import validate_result

    folder, output = Path(folder).resolve(), Path(output).resolve()
    if output.exists() or (folder / "result.json").exists():
        raise ValueError("Retain prior analysis; choose a fresh attempt")
    config = json.loads(_required(folder, "config.json").read_text())
    contract = json.loads(_required(folder, config["measurement_contract"]).read_text())
    if contract["case_id"] != config["case_id"]:
        raise ValueError("Exact case and measurement contract differ")
    joined = verify_original_joins(folder)
    report = finalize(folder, contract, _sha(folder / "native_samples.jsonl"))
    source = report["measurements"]["speed_relation"]["value"]
    videos = [name + ".mkv" for name in
              ("overview", "approach", "reference_corner", "driver_reference")]
    counts = {name: _video_frames(folder / name) for name in videos}
    if set(counts.values()) != {480}:
        raise ValueError("Original camera frame count differs")
    source_kind = report["source_kind"]
    original = source_kind == "original_native_capture"
    requested = {"below_80_mph": 75.0, "inside_80_mph": 79.5,
                 "at_80_mph": 80.0, "above_80_mph": 85.0}[config["case_suffix"]]
    measured = source["derived_peak_mph"]
    derive_recording_channels(folder, config)
    evidence = []
    for channel in config["recording_description"]["channels"]:
        ref = "channels/" + channel["name"] + ".jsonl"
        _required(folder, ref)
        evidence.append({"name": channel["name"], "unit": channel["unit"],
                         "reference": ref})
    for item in config["recording_description"]["context_inputs"]:
        _required(folder, "context.json")
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": "context.json"})
    result = {"case_id": config["case_id"], "measured_values": source,
        "target_checks": [{"target": "saved peak speed against requested case setting",
            "requested": requested, "measured": measured,
            "method": "original 480-frame three-axis Native velocity and pose readback",
            "tolerance": 0.5, "matched": abs(requested - measured) <= 0.5,
            "physical_cause_confirmed": False,
            "cause_evidence": ["native_samples.jsonl", "trace.jsonl",
                               "video_frames.jsonl"]}],
        "setup_confirmed": False, "behavior_attempted": original,
        "maneuver_completed": original,
        "termination_reason": "480 saved source frames checked; territorial and legal review pending",
        "physical_failure_flags": ["territorial_applicability_unverified",
                                   "physical_speed_causation_unverified"],
        "trace_reference": "trace.jsonl", "video_references": videos,
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["recording_description"],
        "recording_evidence": evidence,
        "realized_observables": {"peak_speed_mph": {"value": measured,
            "unit": "mph", "statistic": "maximum sampled speed",
            "method": "three-axis Native velocity norm over 480 original frames",
            "time_window": "entire 24 s attempt", "reference": "native_samples.jsonl"}},
        "provenance_kind": "native" if original else "synthetic_local_diagnostic",
        "diagnostic_fixture": not original,
        "accepted": False, "legal_verdict_claimed": False}
    validate_result(result)
    report.update(format="c111294-saved-speed-analysis-v1", original_joins=joined,
                  video_frames=counts, diagnostic_fixture=not original,
                  analysis_complete=True,
                  limitations=["Territorial applicability and physical speed causation await original review",
                               "No legal or recording acceptance verdict"])
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    (folder / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", type=Path)
    parser.add_argument("--attempt", type=Path)
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--source-sha256")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.attempt:
        report = finalize_attempt(args.attempt, args.output)
    else:
        if not all((args.folder, args.contract, args.source_sha256)):
            parser.error("Saved measurement requires folder, contract and source SHA-256")
        contract = json.loads(args.contract.read_text())
        report = finalize(args.folder, contract, args.source_sha256)
        with args.output.open("x") as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write("\n")
    print(json.dumps({"case_id": report["case_id"], "passed": True,
                      "source_kind": report["source_kind"],
                      "selected": False}, sort_keys=True))
