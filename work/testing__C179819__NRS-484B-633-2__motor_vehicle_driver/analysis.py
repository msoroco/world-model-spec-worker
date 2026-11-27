"""Saved original-source measurements for an exact NRS 484B.633(2) case."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from bridge_observations import measure_crossing, verify_site_bundle


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def structure_crossing_observation(measured, site):
    return {key: measured[key] for key in (
        "structure_kind", "direction", "crossing_original_frames", "original_frame_count")}


def crossing_speed_observation(measured, site):
    return {"declared_maximum_mph": measured["declared_maximum_mph"],
            "observed_crossing_speed_mph": measured["observed_crossing_speed_mph"],
            "structure_safety_judgment": "unresolved"}


def both_signs_observation(measured, site):
    return {"sign_offsets_ft": measured["sign_offsets_ft"],
            "sign_placement_judgment": "unresolved"}


def department_authority_observation(measured, site):
    return {"source_refs": site["authority"],
            "maximum_declaration_source": site["maximum_declaration_source"],
            "sign_causation_judgment": "unresolved"}


def original_capture_observation(measured, site):
    return {"original_frame_count": measured["original_frame_count"],
            "physical_completion": "requires_independent_original_review"}


def build_report(attempt: Path, case_id: str) -> dict:
    attempt = Path(attempt)
    receipt = attempt / "original-source-receipt.json"
    if not receipt.is_file():
        raise ValueError("Missing required source: original-source-receipt.json")
    receipt_data = json.loads(receipt.read_text(encoding="utf-8"))
    if receipt_data.get("case_id") != case_id:
        raise ValueError("original source receipt case differs")
    site_path = attempt / "bridge-site.json"
    trace_path = attempt / "original-motion.jsonl"
    if not site_path.is_file():
        raise ValueError("Missing required source: bridge-site.json")
    if not trace_path.is_file():
        raise ValueError("Missing required source: original-motion.jsonl")
    if receipt_data.get("site_sha256") != sha(site_path) or receipt_data.get("trace_sha256") != sha(trace_path):
        raise ValueError("original source receipt hash differs")
    site = verify_site_bundle(site_path, receipt_data["site_sha256"], case_id)
    rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    marker = attempt / "fixture-provenance.json"
    diagnostic = marker.is_file() and json.loads(marker.read_text()).get("scope", "").startswith("CPU diagnostic")
    expected = 9 if diagnostic else 900
    if bool(receipt_data.get("diagnostic_fixture", False)) != diagnostic:
        raise ValueError("diagnostic source provenance marker differs")
    measured = measure_crossing(site, rows, case_id, expected_frames=expected)
    sources = {"original-source-receipt.json": sha(receipt),
               "bridge-site.json": sha(site_path),
               "original-motion.jsonl": sha(trace_path)}
    methods = (structure_crossing_observation, crossing_speed_observation,
               both_signs_observation, department_authority_observation,
               original_capture_observation)
    return {
        "format": "worker-analysis-report", "case_id": case_id,
        "analysis_complete": True, "legal_verdict_claimed": False,
        "diagnostic_fixture": diagnostic,
        "measurements": {method.__name__: {
            "value": method(measured, site), "method": method.__name__, "sources": sources}
            for method in methods},
    }


def saved_result(attempt: Path, report: dict) -> dict:
    """Build Native-shaped saved evidence without assigning a legal verdict."""
    from worker_exchange.native_output import physical_result, validate_result

    attempt = Path(attempt)
    config = json.loads((attempt / "config.json").read_text(encoding="utf-8"))
    description = config["case"]["recording_description"]
    trace = [json.loads(line) for line in (attempt / "original-motion.jsonl").read_text().splitlines()]
    channels = attempt / "channels"
    channels.mkdir(exist_ok=True)
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        path = channels / (name + ".jsonl")
        with path.open("x", encoding="utf-8") as stream:
            for row in trace:
                if name == "four_camera_pixels":
                    value = {"frame": row["original_frame"],
                             "views": ["overview", "approach", "reference_corner", "driver_reference"]}
                elif name == "observed_crossing_speed_mph":
                    value = row["ego_speed_mps"] * 2.2369362920544
                else:
                    value = row[name]
                stream.write(json.dumps({"time_s": row["time_s"], "value": value}) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(path.relative_to(attempt))})
    context_path = channels / "site-context.json"
    site = json.loads((attempt / "bridge-site.json").read_text())
    context_path.write_text(json.dumps({
        "elevated_structure_ends": [site["end_a_station_m"], site["end_b_station_m"]],
        "declared_structural_maximum": site["declared_maximum_mph"],
        "both_sign_stations": {end: sign["station_m"] for end, sign in site["signs"].items()},
        "department_authority_and_chronology": site["authority"],
        "site_sha256": sha(attempt / "bridge-site.json"),
        "original_source_receipt_sha256": sha(attempt / "original-source-receipt.json"),
        "independent_physical_and_legal_review": "pending"}, sort_keys=True) + "\n")
    for item in description["context_inputs"]:
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": "channels/site-context.json"})
    measured = report["measurements"]["crossing_speed_observation"]["value"]
    requested = measured["declared_maximum_mph"] + config["case"]["requested_speed_delta_from_declared_maximum_mph"]
    observed = measured["observed_crossing_speed_mph"]["maximum"]
    crossing_frames = report["measurements"]["structure_crossing_observation"]["value"]["crossing_original_frames"]
    crossing_times = [row["time_s"] for row in trace if row["original_frame"] in crossing_frames]
    if len(crossing_times) != 2:
        raise ValueError("original crossing time window unavailable")
    result = {
        "case_id": report["case_id"], "measured_values": report["measurements"],
        "target_checks": [{"target": "authored engineering crossing speed maximum",
                           "requested": requested, "measured": observed,
                           "method": "original source-joined crossing speed samples",
                           "tolerance": 5.0, "matched": abs(requested - observed) <= 5,
                           "physical_cause_confirmed": False,
                           "cause_evidence": {"original-motion.jsonl": sha(attempt / "original-motion.jsonl")}}],
        "setup_confirmed": False, "behavior_attempted": False, "maneuver_completed": False,
        "termination_reason": "Saved-only source measurement; physical and legal review pending",
        "physical_failure_flags": [], "trace_reference": "trace.jsonl",
        "video_references": ["overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv"],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description, "recording_evidence": evidence,
        "realized_observables": {},
    }
    result = physical_result(attempt, result)
    result["realized_observables"]["observed_crossing_speed_mph"] = {
        "unit": "mph", "method": "original 20 Hz crossing speed samples converted from m/s",
        "time_window": "entire original crossing", "statistic": "max",
        "reference": "channels/observed_crossing_speed_mph.jsonl",
        "sample_window_s": crossing_times, "value": observed,
    }
    validate_result(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--case")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    case_id = args.case
    if case_id is None:
        case_id = json.loads((args.attempt / "config.json").read_text(encoding="utf-8"))["selected_case_id"]
    if args.output.exists():
        raise ValueError("fresh analysis output required")
    report = build_report(args.attempt, case_id)
    result = saved_result(args.attempt, report)
    (args.attempt / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    report["physical_checks"] = result["physical_checks"]
    report["realized_observables"] = result["realized_observables"]
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
