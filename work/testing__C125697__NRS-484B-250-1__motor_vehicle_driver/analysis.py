"""Saved-only C125697 finalizer over sealed original actor and device history."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import median_opening

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _required(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def _source_manifest(root: Path) -> dict:
    retained = root / "source-manifest.json"
    if not retained.is_file():
        alias = _required(root, "original-source-manifest.json")
        if (root / "fixture-provenance.json").is_file():
            provenance = json.loads((root / "fixture-provenance.json").read_text())
            if provenance.get("diagnostic_fixture") is not True or provenance.get("physical_acceptance_claimed") is not False:
                raise ValueError("diagnostic source provenance differs")
        else:
            seal = json.loads(_required(root, "capture-seal.json").read_text())
            if (seal.get("provenance_kind") != "native" or
                    seal.get("sources", {}).get("original-source-manifest.json") != _sha(alias)):
                raise ValueError("Native original-source alias is unsealed")
        retained.write_bytes(alias.read_bytes())
    return json.loads(retained.read_text())


def measure_crossing_highways(scene: dict) -> dict:
    return {"crossing_id": scene["crossing"]["id"],
            "crossing_kind": scene["crossing"]["kind"],
            "ego_highway": scene["ego_highway"],
            "other_highway": scene["other_highway"],
            "distinct_highways": scene["ego_highway"] != scene["other_highway"]}


def measure_other_entry(measured: dict) -> dict:
    return {"other_entry_frame": measured["entry_frames"]["other"],
            "ego_entry_frame": measured["entry_frames"]["ego"],
            "other_entered_before_ego": measured["other_entered_before_ego"],
            "native_first_frame_id": measured["native_first_frame_id"]}


def measure_ego_response(measured: dict) -> dict:
    return {"ego_entry_frame": measured["entry_frames"]["ego"],
            "other_exit_frame": measured["exit_frames"]["other"],
            "ego_waited_until_other_exit": measured["ego_waited_until_other_exit"]}


def measure_device_context(scene: dict, measured: dict) -> dict:
    return {"governing_signal": scene["governing_signal"],
            "signal_inoperative_all_frames": measured["signal_inoperative_all_frames"],
            "subsection_4_applicability_review": scene.get("subsection_4_applicability_review"),
            "legal_applicability": "unresolved"}


def measure_opposing_turn_context(scene: dict) -> dict:
    return {"ego_route_xy_m": scene["ego_route_xy_m"],
            "other_route_xy_m": scene["other_route_xy_m"],
            "opposing_left_turn_excluded_source": scene.get("opposing_left_turn_excluded_source"),
            "legal_exclusion": "unresolved"}


def analyze(attempt: Path, output: Path) -> dict:
    root = Path(attempt)
    config = json.loads(_required(root, "config.json").read_text())
    construction = json.loads(_required(root, "construction.json").read_text())
    case = config["selected_case_id"]
    if construction.get("case_id") != case or case not in (
            "testing__C125697__NRS-484B-250-1__motor_vehicle_driver__precedence",
            "testing__C125697__NRS-484B-250-1__motor_vehicle_driver__advance"):
        raise ValueError("wrong selected median-opening construction")
    scene = json.loads(_required(root, "scene.json").read_text())
    manifest = _source_manifest(root)
    _required(root, manifest["sources"]["native_trace"]["path"])
    diagnostic = (root / "fixture-provenance.json").is_file()
    audited = median_opening.audit_saved_sources(root, manifest, scene,
                                                 diagnostic_fixture=diagnostic)
    measured = audited["observations"]
    if not measured["other_entered_before_ego"]:
        raise ValueError("original history lost earlier other entry")
    original = json.loads(_required(root, manifest["sources"]["native_trace"]["path"]).read_text())
    frames = original["frames"]
    mapping = [json.loads(line) for line in _required(root, "video_frames.jsonl").read_text().splitlines()]
    trace = [json.loads(line) for line in _required(root, "trace.jsonl").read_text().splitlines()]
    if len(mapping) != len(trace) or len(trace) != len(frames):
        raise ValueError("original trace/frame-map count differs")
    for index, (row, frame, video) in enumerate(zip(trace, frames, mapping)):
        if (row.get("frame") != frame["native_frame_id"] or
                row.get("time_s") != frame["native_elapsed_seconds"] or
                video.get("video_frame") != index or
                video.get("carla_frame") != row["frame"] or
                video.get("time_s") != row["time_s"]):
            raise ValueError("original trace/frame-map identity differs")
    description = construction["recording_description"]
    if description != next(c["recording_description"] for c in json.loads(
            _required(root, "case-plan.json").read_text())["cases"] if c["case_id"] == case):
        raise ValueError("selected recording description changed")
    channel_dir = root / "channels"
    channel_dir.mkdir(exist_ok=False)
    body_path = channel_dir / "intersection_body_history.jsonl"
    signal_path = channel_dir / "governing_signal_readback.jsonl"
    body_path.write_text("".join(json.dumps({
        "time_s": row["native_elapsed_seconds"],
        "value": {"ego": row["ego"], "other": row["other"]}}) + "\n"
        for row in frames))
    signal_path.write_text("".join(json.dumps({
        "time_s": row["native_elapsed_seconds"],
        "value": row["signal_readback"]}) + "\n" for row in frames))
    site_path = channel_dir / "reviewed_site_device_highway_packet.json"
    site_path.write_text(json.dumps({"reviewed_site_device_highway_packet": {
        "crossing": scene["crossing"], "ego_highway": scene["ego_highway"],
        "other_highway": scene["other_highway"], "source_sha256": audited["source_sha256"]}},
        indent=2) + "\n")
    approach_path = channel_dir / "approach_and_turn_intent.json"
    approach_path.write_text(json.dumps({"approach_and_turn_intent": {
        "ego_route_xy_m": scene["ego_route_xy_m"],
        "other_route_xy_m": scene["other_route_xy_m"],
        "opposing_left_turn_excluded_source": scene.get("opposing_left_turn_excluded_source"),
        "legal_judgment": "unresolved"}}, indent=2) + "\n")
    refs = {
        "intersection_body_history": body_path,
        "governing_signal_readback": signal_path,
        "reviewed_site_device_highway_packet": site_path,
        "approach_and_turn_intent": approach_path,
    }
    evidence = [{"name": item["name"], "unit": item["unit"],
                 "reference": str(refs[item["name"]].relative_to(root))}
                for item in description["channels"] + description["context_inputs"]]
    requested = case.endswith("__precedence")
    observed = measured["ego_waited_until_other_exit"]
    checks = [
        {"target": "other_entered_before_ego", "requested": True,
         "measured": measured["other_entered_before_ego"],
         "method": "original footprint entry transitions", "tolerance": 0,
         "matched": measured["other_entered_before_ego"],
         "physical_cause_confirmed": False,
         "cause_evidence": audited["source_sha256"]},
        {"target": "ego_waited_until_other_exit", "requested": requested,
         "measured": observed, "method": "original ego entry and other exit transitions",
         "tolerance": 0, "matched": requested == observed,
         "physical_cause_confirmed": False,
         "cause_evidence": audited["source_sha256"]},
    ]
    result = {
        "case_id": case,
        "measured_values": measured, "target_checks": checks,
        "setup_confirmed": True, "behavior_attempted": True,
        "maneuver_completed": True,
        "termination_reason": f"{len(frames)} source frames analyzed; physical and legal review pending",
        "physical_failure_flags": [],
        "trace_reference": "trace.jsonl",
        "video_references": [manifest["sources"]["camera_" + name]["path"] for name in CAMERAS],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description,
        "recording_evidence": evidence,
        "realized_observables": {},
        "diagnostic_fixture": diagnostic,
        "physical_acceptance_claimed": False,
        "legal_judgment": "unresolved",
    }
    (root / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    measurement_specs = {
        "crossing_highways": ("measure_crossing_highways", measure_crossing_highways(scene),
                              ["scene.json", "opendrive.xodr", "highway_identity.json"]),
        "other_entry": ("measure_other_entry", measure_other_entry(measured),
                        ["native_trace.json", "scene.json"]),
        "ego_response": ("measure_ego_response", measure_ego_response(measured),
                         ["native_trace.json", "scene.json"]),
        "device_context": ("measure_device_context", measure_device_context(scene, measured),
                           ["native_trace.json", "scene.json", "device_inventory.json"]),
        "opposing_turn_context": ("measure_opposing_turn_context", measure_opposing_turn_context(scene),
                                  ["scene.json", "native_trace.json"]),
    }
    measurements = {key: {"method": method, "value": value,
                          "sources": {name: _sha(_required(root, name)) for name in inputs}}
                    for key, (method, value, inputs) in measurement_specs.items()}
    report = {
        "format": "worker-analysis-report", "case_id": case,
        "measurements": measurements,
        "diagnostic_fixture": diagnostic,
        "legal_verdict_claimed": False,
        "limitations": [
            "Original highway/device context and subsection 4 applicability need independent review.",
            "Diagnostic fixtures do not establish physical motion or camera visibility.",
        ],
    }
    Path(output).write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps({"case_id": analyze(args.attempt, args.output)["case_id"]}))


if __name__ == "__main__":
    main()
