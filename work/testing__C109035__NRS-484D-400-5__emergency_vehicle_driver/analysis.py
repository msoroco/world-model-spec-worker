"""Saved-only diagnostic finalization for exact emergency warning cases."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
from pathlib import Path

from saved_finalizer import measure as _measure


def measure(folder: Path, *, case_id: str) -> dict:
    """Measure sealed original sources without deciding legal compliance."""
    return _measure(folder, case_id=case_id)


def _rows(path: Path) -> list[dict]:
    if not path.is_file():
        raise ValueError("Missing required source: " + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def materialize_diagnostic_archives(attempt: Path) -> None:
    """Rebuild synthetic camera ZIP bytes from a hash-bound text fixture source."""
    encoded = attempt / "diagnostic-archives.json"
    if not encoded.is_file():
        return
    provenance = json.loads((attempt / "acquisition-provenance.json").read_text())
    if (provenance.get("provenance_kind") != "synthetic_fixture" or
            provenance.get("diagnostic_fixture") is not True):
        raise ValueError("Diagnostic camera archives require synthetic provenance")
    document = json.loads(encoded.read_text())
    if (document.get("format") != "c109035-diagnostic-archives-v1" or
            set(document.get("archives", {})) != {name + ".zip" for name in
                                                 ("overview", "approach", "reference_corner", "driver_reference")}):
        raise ValueError("Diagnostic camera archive inventory differs")
    for name, record in document["archives"].items():
        raw = base64.b64decode(record["base64"], validate=True)
        if hashlib.sha256(raw).hexdigest() != record["sha256"]:
            raise ValueError("Diagnostic camera archive bytes differ")
        path = attempt / name
        if path.exists():
            raise ValueError("Diagnostic camera archive shadows an original source")
        path.write_bytes(raw)


def run(attempt: Path, output: Path) -> dict:
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output != attempt / "analysis-report.json" or output.exists() or (attempt / "result.json").exists():
        raise ValueError("Saved analysis requires a fresh in-attempt report")
    config = json.loads((attempt / "config.json").read_text())
    case_id = config["selected_case_id"]
    if case_id != config["case"]["case_id"]:
        raise ValueError("Selected exact case differs")
    materialize_diagnostic_archives(attempt)
    measured = measure(attempt, case_id=case_id)
    trace = _rows(attempt / "trace.jsonl")
    mapping = _rows(attempt / "video_frames.jsonl")
    if len(trace) != 900 or len(mapping) != 900:
        raise ValueError("Original trace/frame map incomplete")
    actors = _rows(attempt / "actor_trace.jsonl")
    devices = _rows(attempt / "device_trace.jsonl")
    dispatch = json.loads((attempt / "dispatch_context.json").read_text())
    equipment = json.loads((attempt / "equipment_record.json").read_text())
    for index, (point, mapped, actor, device) in enumerate(zip(trace, mapping, actors, devices)):
        frame = actor["native_frame"]
        if (point.get("frame") != frame or mapped.get("carla_frame") != frame or
                mapped.get("video_frame") != index or mapped.get("native_frame") != frame or
                device.get("native_frame") != frame or
                point.get("time_s") != mapped.get("time_s")):
            raise ValueError("Original Native frame join differs")
    status = json.loads((attempt / "native-run-status.json").read_text())
    if (status.get("case_id") != case_id or status.get("errors") != [] or
            status.get("restoration", {}).get("restored") is not True):
        raise ValueError("Original Native restoration/status differs")
    for name in ("overview", "approach", "reference_corner", "driver_reference"):
        if not (attempt / (name + ".mkv")).is_file():
            raise ValueError("Missing required source: " + name + ".mkv")
    recording = next(case for case in json.loads((attempt / "proposals/cases.json").read_text())["cases"]
                     if case["case_id"] == case_id)["recording_description"] if (attempt / "proposals/cases.json").is_file() else None
    if recording is None:
        # The materialized construction embeds the exact selected description.
        construction = json.loads((attempt / "construction.json").read_text())
        recording = construction["recording_description"]
    channel_rows = {
        "siren_active": [row["siren_active"] for row in devices],
        "warning_lamp_active": [row["warning_lamp_active"] for row in devices],
        "ego_position": [[row["ego"][key] for key in ("x_m", "y_m", "z_m")] for row in actors],
        "pedestrian_position": [[row["pedestrian"][key] for key in ("x_m", "y_m", "z_m")] for row in actors],
        "camera_frame_identity": [row["native_frame"] for row in devices],
        "original_siren_and_warning_lamp_state": [
            {key: row[key] for key in ("siren_active", "warning_lamp_active",
                                        "siren_commanded", "warning_lamp_commanded")}
            for row in devices],
        "qualifying_event_and_temporal_relation": [
            {"documented_event": dispatch["event"],
             "in_documented_interval": dispatch["event_interval_frames"][0] <= index <=
                                       dispatch["event_interval_frames"][1],
             "siren_active": row["siren_active"]}
            for index, row in enumerate(devices)],
        "pedestrian_approach_relation": [
            {"ego_xy_m": [row["ego"]["x_m"], row["ego"]["y_m"]],
             "pedestrian_xy_m": [row["pedestrian"]["x_m"], row["pedestrian"]["y_m"]],
             "separation_m": math.hypot(row["ego"]["x_m"] - row["pedestrian"]["x_m"],
                                         row["ego"]["y_m"] - row["pedestrian"]["y_m"])}
            for row in actors],
        "equipment_and_authorization": [
            {key: equipment[key] for key in ("authorization_source",
                                           "device_installation_source",
                                           "audibility_500ft_status")}
            for _ in devices],
    }
    channel_dir = attempt / "channels"
    channel_dir.mkdir(exist_ok=False)
    evidence = []
    for item in recording["channels"]:
        name = item["name"]
        path = channel_dir / (name + ".jsonl")
        path.write_text("".join(json.dumps({"time_s": index / 20, "value": value}) + "\n"
                                for index, value in enumerate(channel_rows[name])))
        evidence.append({"name": name, "unit": item["unit"],
                         "reference": "channels/" + path.name})
    for item in recording["context_inputs"]:
        name = item["name"]
        source_path = attempt / (name + ".json")
        if not source_path.is_file():
            raise ValueError("Missing required source: " + source_path.name)
        context_path = channel_dir / (name + ".json")
        context_path.write_text(json.dumps({name: json.loads(source_path.read_text())}) + "\n")
        evidence.append({"name": name, "unit": item["unit"],
                         "reference": "channels/" + context_path.name})
    comparison = {"target": "requested_siren", "requested": config["case"]["siren"],
                  "measured": bool(measured["measurements"]["temporal_siren_relation"]["value"]["all_siren_frames_within_documented_event"])
                  if config["case"]["siren"] else False,
                  "method": "sealed original device and dispatch source join",
                  "tolerance": 0, "matched": False,
                  "physical_cause_confirmed": False,
                  "cause_evidence": "diagnostic source only"}
    comparison["matched"] = comparison["requested"] == comparison["measured"]
    result = {"case_id": case_id, "measured_values": measured["measurements"],
              "target_checks": [comparison], "setup_confirmed": False,
              "behavior_attempted": True, "maneuver_completed": True,
              "termination_reason": "900-frame diagnostic window",
              "physical_failure_flags": ["physical acceptance requires Native review"],
              "trace_reference": "trace.jsonl", "video_frame_map_reference": "video_frames.jsonl",
              "video_references": [name + ".mkv" for name in
                                   ("overview", "approach", "reference_corner", "driver_reference")],
              "recording_description": recording, "recording_evidence": evidence,
              "realized_observables": {}, "physical_acceptance_claimed": False}
    (attempt / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    report = {"format": "c109035-saved-analysis-v1", "case_id": case_id,
              "measurements": measured["measurements"],
              "source_hashes": {name: _hash(attempt / name) for name in
                                ("device_trace.jsonl", "actor_trace.jsonl",
                                 "dispatch_context.json", "equipment_record.json")},
              "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.attempt, args.output), indent=2))
