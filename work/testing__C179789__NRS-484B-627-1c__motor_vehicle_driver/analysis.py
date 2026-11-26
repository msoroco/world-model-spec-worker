"""Saved-only source-bound route analysis; physical and legal claims stay separate."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def required(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def build_report(root: Path) -> dict:
    root = Path(root)
    config = json.loads(required(root, "config.json").read_text())
    case_id = config["selected_case_id"]
    provenance = root / "fixture-provenance.json"
    diagnostic = provenance.is_file()
    if diagnostic:
        declaration = json.loads(provenance.read_text())
        if declaration.get("diagnostic_fixture") is not True or declaration.get("physical_acceptance_claimed") is not False:
            raise ValueError("diagnostic route provenance invalid")
    site_path = required(root, "original-site.json")
    motion_path = required(root, "original-route-motion.json")
    site = json.loads(site_path.read_text())
    packet = json.loads(motion_path.read_text())
    if packet.get("case_id") != case_id or packet.get("source_kind") != (
            "diagnostic_fixture" if diagnostic else "original_native"):
        raise ValueError("selected route source identity differs")
    if packet.get("site_sha256") != sha(site_path):
        raise ValueError("route motion is not bound to original site")
    rows = packet.get("samples", [])
    if len(rows) != (9 if diagnostic else 900):
        raise ValueError("source route frame count differs")
    mapping = [json.loads(line) for line in required(root, "video_frames.jsonl").read_text().splitlines()]
    if len(mapping) != len(rows) or any(
            row.get("original_frame") != frame.get("carla_frame") or
            row.get("time_s") != frame.get("time_s") or
            frame.get("video_frame") != index
            for index, (row, frame) in enumerate(zip(rows, mapping))):
        raise ValueError("route motion and original frame map differ")
    ids = {(row.get("ego_id"), row.get("follower_id")) for row in rows}
    if len(ids) != 1 or any(not pair[0] or not pair[1] or pair[0] == pair[1] for pair in ids):
        raise ValueError("original participant identity differs")
    if any(row.get("following_gap_m", 0) <= 0 or row.get("ego_speed_mps") is None or
           row.get("follower_speed_mps") is None or
           row.get("actual_route_choice") not in ("main", "alternate") for row in rows):
        raise ValueError("original follower or route observation missing")
    if rows[-1]["actual_route_choice"] != config["case"]["target"]["route_choice"]:
        raise ValueError("terminal observed route differs from selected target")
    if not diagnostic:
        acquisition = json.loads(required(root, "original-route-acquisition.json").read_text())
        if acquisition.get("site_sha256") != sha(site_path) or acquisition.get("motion_sha256") != sha(motion_path):
            raise ValueError("original route acquisition source hash differs")
        if not site.get("reviewed_original_site"):
            raise ValueError("original reviewed route site missing")
    common = {"original-site.json": sha(site_path),
              "original-route-motion.json": sha(motion_path)}
    measurements = {
        "highway_vehicle_context": {"value": {
            "reviewed_original_site": bool(site.get("reviewed_original_site")) and not diagnostic,
            "site_sha256": sha(site_path), "case_id": case_id,
            "diagnostic_fixture": diagnostic}, "method": "build_report",
            "sources": {"original-site.json": common["original-site.json"]}},
        "following_motion_measurement": {"value": {
            "frame_count": len(rows), "ego_id": rows[0]["ego_id"],
            "follower_id": rows[0]["follower_id"],
            "minimum_gap_m": min(row["following_gap_m"] for row in rows),
            "mean_ego_speed_mps": sum(row["ego_speed_mps"] for row in rows) / len(rows),
            "mean_follower_speed_mps": sum(row["follower_speed_mps"] for row in rows) / len(rows),
            "impeding_judgment": None, "immediately_behind_judgment": None},
            "method": "build_report",
            "sources": {"original-route-motion.json": common["original-route-motion.json"]}},
        "alternate_route_measurement": {"value": {
            "terminal_actual_route": rows[-1]["actual_route_choice"],
            "controlled_access_declared": rows[-1].get("controlled_access"),
            "alternate_restriction_state": rows[-1].get("alternate_restriction_state"),
            "possible_route_judgment": None, "legal_judgment": None},
            "method": "build_report", "sources": common}}
    return {"format": "worker-analysis-report", "case_id": case_id,
            "measurements": measurements, "selected_target_matched": True,
            "analysis_complete": True, "source_decode_passed": True,
            "diagnostic_fixture": diagnostic, "legal_verdict_claimed": False,
            "limitations": ["Requested speed and alternate entry lead are engineering coordinates only.",
                            "Original motion does not decide legal impediment or whether an alternate was possible."]}


def saved_result(root: Path, report: dict) -> dict:
    from worker_exchange.native_output import physical_result, validate_result
    config = json.loads((root / "config.json").read_text())
    construction = json.loads((root / "construction.json").read_text())
    rows = json.loads((root / "original-route-motion.json").read_text())["samples"]
    description = construction["recording_description"]
    streams = {
        "native_frame": [row["original_frame"] for row in rows],
        "ego_motion": [{"xy": row.get("ego_xy"), "speed_mps": row["ego_speed_mps"]} for row in rows],
        "follower_motion": [{"xy": row.get("follower_xy"), "gap_m": row["following_gap_m"],
                             "speed_mps": row["follower_speed_mps"]} for row in rows],
        "route_choice": [row["actual_route_choice"] for row in rows],
        "map_classification": [row.get("controlled_access") for row in rows],
        "journey_context": [row.get("alternate_restriction_state") for row in rows],
        "four_camera_frames": [row["camera_frames"] for row in rows],
        "ego_speed_mps": [row["ego_speed_mps"] for row in rows],
        "alternate_entry_lead_m": [row.get("alternate_entry_lead_m") for row in rows],
    }
    channels = root / "channels"
    channels.mkdir(exist_ok=False)
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        path = channels / (name + ".jsonl")
        path.write_text("\n".join(json.dumps({"time_s": row["time_s"], "value": value})
                     for row, value in zip(rows, streams[name])) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(path.relative_to(root))})
    context = {"highway": "SHA-bound original site", "controlled_access": rows[-1].get("controlled_access"),
               "driver_and_vehicle": [rows[0]["ego_id"], rows[0]["follower_id"]],
               "alternate_restriction": rows[-1].get("alternate_restriction_state")}
    context_path = channels / "context.json"
    context_path.write_text(json.dumps(context, sort_keys=True) + "\n")
    for item in description["context_inputs"]:
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": str(context_path.relative_to(root))})
    result = {"case_id": config["selected_case_id"], "measured_values": report["measurements"],
              "target_checks": [{"target": "source-observed route and follower attempt",
                                 "requested": config["case"]["target"],
                                 "measured": report["measurements"]["alternate_route_measurement"]["value"],
                                 "method": "saved source-bound 20 Hz route measurement",
                                 "tolerance": 0, "matched": True,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": report["measurements"]["alternate_route_measurement"]["sources"]}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "Saved route source assessment pending physical review",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in
                                   ("overview", "approach", "reference_corner", "driver_reference")],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": evidence,
              "realized_observables": {}}
    result = physical_result(root, result)
    result["realized_observables"].update({
        "ego_speed_mps": {"value": sum(row["ego_speed_mps"] for row in rows) / len(rows),
            "unit": "m/s", "method": "original 20 Hz ego speed readback",
            "time_window": "entire original 45-second episode", "statistic": "mean",
            "sample_window_s": [rows[0]["time_s"], rows[-1]["time_s"]],
            "reference": "channels/ego_speed_mps.jsonl"},
        "alternate_entry_lead_m": {"value": rows[0]["alternate_entry_lead_m"],
            "unit": "m", "method": "original Native route-station distance to selected alternate entry",
            "time_window": "entire original 45-second episode", "statistic": "first",
            "sample_window_s": [rows[0]["time_s"], rows[-1]["time_s"]],
            "reference": "channels/alternate_entry_lead_m.jsonl"}})
    validate_result(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.attempt)
    report = build_report(root)
    result = saved_result(root, report)
    report["physical_checks"] = result["physical_checks"]
    report["realized_observables"] = result["realized_observables"]
    (root / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
