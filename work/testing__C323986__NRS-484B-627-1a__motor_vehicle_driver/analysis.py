"""Saved-source measurement report for the exact conditional right-side duty."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from finalize_original import finalize
from reviewed_scene import ASSIGNMENT, VARIANTS


def _source(attempt: Path, name: str) -> tuple[dict, str]:
    path = attempt / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def build_report(attempt: Path, case_id: str) -> dict:
    attempt = Path(attempt)
    if case_id not in {ASSIGNMENT + "__" + suffix for suffix in VARIANTS}:
        raise ValueError("exact selected case required")
    site, site_sha = _source(attempt, "original-site.json")
    if site.get("case_id") != case_id or not site.get("site_ref_sha256"):
        raise ValueError("original exact site source mismatch")
    measured = finalize(attempt, case_id)
    observations = measured["observations"]
    motion_sha = measured["source"]["motion_sha256"]
    relation_sha = measured["source"]["relation_sha256"]
    frame_sha = measured["source"]["frame_map_sha256"]
    motion = {"original-motion.json": motion_sha,
              "original-relation.json": relation_sha,
              "original-frame-map.json": frame_sha}
    site_source = {"original-site.json": site_sha}
    right_source = dict(motion, **site_source)
    count = len(observations)
    measurements = {
        "following_motion_measurement": {
            "value": {"frame_count": count,
                      "immediate_follower_frames": sum(row["immediately_behind_readback"] for row in observations),
                      "mean_subject_speed_mps": sum(row["subject_speed_mps"] for row in observations) / count,
                      "mean_follower_speed_mps": sum(row["follower_speed_mps"] for row in observations) / count,
                      "first_gap_m": observations[0]["follower_along_route_body_gap_m"],
                      "last_gap_m": observations[-1]["follower_along_route_body_gap_m"]},
            "method": "build_report", "sources": motion},
        "right_side_and_obstruction_measurement": {
            "value": {"frame_count": count,
                      "first_ego_to_paved_edge_m": observations[0]["ego_to_paved_right_edge_m"],
                      "last_ego_to_paved_edge_m": observations[-1]["ego_to_paved_right_edge_m"],
                      "first_obstruction_to_paved_edge_m": observations[0]["obstruction_to_paved_right_edge_m"],
                      "lateral_obstruction_overlap_frames": sum(row["body_overlaps_obstruction_laterally"] for row in observations),
                      "reviewed_site_ref_sha256": site["site_ref_sha256"]},
            "method": "build_report", "sources": right_source},
        "nrs_484b_630_context": {
            "value": {"cross_reference": "NRS 484B.630",
                      "applicability": "unresolved by this physical measurement",
                      "context_source": site.get("nrs_484b_630_context_source", "not provided"),
                      "original_site_ref_sha256": site["site_ref_sha256"]},
            "method": "build_report", "sources": site_source},
    }
    return {"format": "worker-analysis-report", "case_id": case_id,
            "measurements": measurements,
            "original_frame_count": count,
            "original_observations": observations,
            "diagnostic_fixture": measured["diagnostic_fixture"],
            "legal_verdict_claimed": False,
            "analysis_complete": True}


def saved_result(attempt: Path, report: dict) -> dict:
    from worker_exchange.native_output import physical_result, validate_result

    attempt = Path(attempt)
    config = json.loads((attempt / "config.json").read_text(encoding="utf-8"))
    construction = json.loads((attempt / "construction.json").read_text(encoding="utf-8"))
    case_id = config["selected_case_id"]
    if construction["case_id"] != case_id or report["case_id"] != case_id:
        raise ValueError("saved construction and report case differ")
    rows = report["original_observations"]
    description = construction["recording_description"]
    frame_map = json.loads((attempt / "original-frame-map.json").read_text(encoding="utf-8"))["frames"]
    streams = {
        "original_actor_motion": [{"subject_speed_mps": r["subject_speed_mps"],
            "follower_speed_mps": r["follower_speed_mps"],
            "subject_station_m": r["subject_station_m"]} for r in rows],
        "separate_follower_relation": [{"immediately_behind": r["immediately_behind_readback"],
            "body_gap_m": r["follower_along_route_body_gap_m"]} for r in rows],
        "two_way_lane_count": [r["one_lane_each_direction_readback"] for r in rows],
        "paved_right_edge": [r["paved_right_edge_m"] for r in rows],
        "highway_right_edge": [r["highway_right_edge_m"] for r in rows],
        "subject_body_footprint": [{"right_edge_m": r["ego_body_right_edge_m"],
            "center_m": r["ego_body_center_m"]} for r in rows],
        "roadside_obstruction_geometry": [{"lateral_edges_m": r["obstruction_lateral_edges_m"],
            "station_m": r["obstruction_station_m"]} for r in rows],
        "four_view_frame_map": [frame["camera_frames"] for frame in frame_map],
        "nrs_484b_630_applicability_context": [{"cross_reference": "NRS 484B.630",
            "applicability": None} for _ in rows],
        "following_progress": [{"subject_speed_mps": r["subject_speed_mps"],
            "follower_speed_mps": r["follower_speed_mps"],
            "body_gap_m": r["follower_along_route_body_gap_m"]} for r in rows],
        "right_side_clearance": [r["ego_to_paved_right_edge_m"] for r in rows],
        "body_right_position": [r["ego_to_highway_right_edge_m"] for r in rows],
        "subject_speed_mps": [r["subject_speed_mps"] for r in rows],
        "ego_to_paved_right_edge_m": [r["ego_to_paved_right_edge_m"] for r in rows],
        "ego_to_highway_right_edge_m": [r["ego_to_highway_right_edge_m"] for r in rows],
        "ego_speed_mps": [r["subject_speed_mps"] for r in rows],
        "paved_right_edge_m": [r["paved_right_edge_m"] for r in rows],
        "ego_path_offset_m": [r["ego_body_center_m"] for r in rows],
    }
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        if name not in streams:
            raise ValueError("unsupported exact recording channel: " + name)
        path = channels / (name + ".jsonl")
        path.write_text("\n".join(json.dumps({"time_s": r["time_s"], "value": value})
                     for r, value in zip(rows, streams[name])) + "\n", encoding="utf-8")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(path.relative_to(attempt))})
    site = json.loads((attempt / "original-site.json").read_text(encoding="utf-8"))
    context = {
        "reviewed original two-way highway and NRS 484B.630 context": site,
        "original_highway_and_cross_reference": site,
    }
    context_path = channels / "context.json"
    context_path.write_text(json.dumps(context, sort_keys=True) + "\n", encoding="utf-8")
    for item in description["context_inputs"]:
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": str(context_path.relative_to(attempt))})
    measured = report["measurements"]
    result = {"case_id": case_id, "measured_values": measured,
        "target_checks": [{"target": "original right-side path, follower and obstruction observation",
            "requested": config["case"], "measured": measured["right_side_and_obstruction_measurement"]["value"],
            "method": "sealed original 20 Hz physical measurement",
            "tolerance": 0, "matched": False, "physical_cause_confirmed": False,
            "cause_evidence": measured["right_side_and_obstruction_measurement"]["sources"]}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "Original physical and legal review pending",
        "physical_failure_flags": [], "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in
            ("overview", "approach", "reference_corner", "driver_reference")],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description, "recording_evidence": evidence,
        "realized_observables": {}}
    result = physical_result(attempt, result)
    definitions = {
        "ego_speed_mps": ("m/s", "mean original 20 Hz subject speed readback", "mean", streams["ego_speed_mps"]),
        "paved_right_edge_m": ("m", "first original paved right-edge readback", "first", streams["paved_right_edge_m"]),
        "ego_path_offset_m": ("m", "mean original subject body center relative travel lane", "mean", streams["ego_path_offset_m"]),
    }
    for name, (unit, method, statistic, values) in definitions.items():
        value = values[0] if statistic == "first" else sum(values) / len(values)
        result["realized_observables"][name] = {
            "value": value, "unit": unit, "method": method,
            "time_window": "full original 45-second episode", "statistic": statistic,
            "sample_window_s": [rows[0]["time_s"], rows[-1]["time_s"]],
            "reference": "channels/" + name + ".jsonl"}
    validate_result(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("fresh saved-source analysis report required")
    case_id = args.case or json.loads((args.attempt / "config.json").read_text(encoding="utf-8"))["selected_case_id"]
    report = build_report(args.attempt, case_id)
    result = saved_result(args.attempt, report)
    report["physical_checks"] = result["physical_checks"]
    report["realized_observables"] = result["realized_observables"]
    (args.attempt / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
