"""Saved-only source measurement for backing into an intersection or around a corner."""

import argparse
import hashlib
import json
from pathlib import Path

from reverse_alternatives import analyze


ASSIGNMENT = "testing__C215286__NRS-484B-113-2__motor_vehicle_driver"
CASES = {
    ASSIGNMENT + "__reverse_into_intersection": ("intersection", True),
    ASSIGNMENT + "__reverse_stops_before_intersection": ("intersection", False),
    ASSIGNMENT + "__reverse_around_street_corner": ("street_corner", True),
    ASSIGNMENT + "__reverse_stops_before_street_corner": ("street_corner", False),
}
CAMERAS = ("overview.mkv", "approach.mkv", "reference_corner.mkv",
           "driver_reference.mkv")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finalize(attempt, output):
    from worker_exchange.native_output import physical_result, write_result

    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / "result.json").exists() or (attempt / "channels").exists():
        raise ValueError("Use a fresh attempt for saved finalization")
    config = json.loads((attempt / "config.json").read_text())
    case_id = config.get("selected_case_id")
    if case_id not in CASES:
        raise ValueError("Exact C215286 alternative case required")
    alternative, expected_entry = CASES[case_id]
    site_name = alternative + ("_site.json" if expected_entry else "_stop_site.json")
    for name in ("config.json", site_name, "reverse_site_context.json",
                 "reverse_history.jsonl", "video_frames.jsonl", "trace.jsonl",
                 "capture/evidence.jsonl", *CAMERAS):
        if not (attempt / name).is_file():
            raise ValueError("Missing required original source: " + name)
    site = json.loads((attempt / site_name).read_text())
    context = json.loads((attempt / "reverse_site_context.json").read_text())
    site_source = context.get("site_packet_source")
    if (not isinstance(site_source, dict) or site_source.get("path") != site_name
            or site_source.get("sha256") != _sha(attempt / site_name)):
        raise ValueError("Saved site packet source differs from original capture")
    polygon_key = ("intersection_polygon_xy_m" if alternative == "intersection"
                   else "street_corner_region_xy_m")
    if (site.get("alternative") != alternative or
            site.get("expected_entry") is not expected_entry or
            context.get("expected_entry") is not expected_entry or
            site.get("region_polygon_xy_m") != context.get(polygon_key) or
            site.get("native_map_id") != context.get("native_map_id")):
        raise ValueError("Saved site context differs from selected construction")
    report = analyze(attempt, alternative)
    if config.get("rate_hz") != 20 or config.get("duration_s") != 45:
        raise ValueError("Selected alternative requires 20 Hz for 45 seconds")
    if len(report["samples"]) != 900:
        raise ValueError("Selected alternative requires 900 joined original frames")
    description = config.get("recording_description")
    if not isinstance(description, dict) or not description.get("channels"):
        raise ValueError("Selected recording description required")
    observed_entry = report["reverse_body_enters_region"]
    observed_turn = (abs(report["heading_change_while_in_corner_deg"]) > 0
                     if alternative == "street_corner" else None)
    matched = (observed_entry == expected_entry and report["backward_motion_observed"]
               and (alternative != "street_corner" or
                    (observed_turn == expected_entry and
                     (not expected_entry or report["continuous_reverse_turn_in_corner"]))))
    channels = attempt / "channels"
    channels.mkdir()
    extract = {
        "native_reverse": lambda row: row["native_reverse"],
        "backward_motion": lambda row: row["backward_motion_observed"],
        "region_overlap": lambda row: row["body_intersects_region"],
    }
    evidence = []
    for name, getter in extract.items():
        destination = channels / (name + ".jsonl")
        with destination.open("x") as stream:
            for sample in report["samples"]:
                stream.write(json.dumps({"original_frame": sample["frame"],
                                         "time_s": sample["time_s"],
                                         "value": getter(sample)},
                                        separators=(",", ":")) + "\n")
        evidence.append({"name": name, "unit": "boolean",
                         "reference": "channels/" + destination.name})
    (channels / "reverse_site_context.json").write_text(
        json.dumps({"reverse_site_context": context}, indent=2) + "\n")
    evidence.append({"name": "reverse_site_context", "unit": "structured record",
                     "reference": "channels/reverse_site_context.json"})
    check = {
        "target": "observed backward body entry into sourced " + alternative + " region",
        "requested": expected_entry, "measured": bool(observed_entry),
        "method": "original reverse readback, 20 Hz complete-body displacement and sourced region; observed heading change for corner",
        "tolerance": 0, "matched": bool(matched),
        "physical_cause_confirmed": False,
        "cause_evidence": ["reverse_history.jsonl", "video_frames.jsonl",
                           "reverse_site_context.json", site_name],
    }
    result = {
        "case_id": case_id,
        "measured_values": {"reverse_body_enters_region": report["reverse_body_enters_region"],
                            "backward_motion_observed": report["backward_motion_observed"],
                            "heading_change_while_in_corner_deg": report.get("heading_change_while_in_corner_deg")},
        "target_checks": [check],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "saved source analysis; physical site and legal review remain separate",
        "physical_failure_flags": ["actual Native site geometry and camera pixels require independent review"],
        "trace_reference": "trace.jsonl", "video_references": list(CAMERAS),
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description, "recording_evidence": evidence,
        "source_evidence_hashes": report["source_sha256"],
        "capture_evidence_sha256": _sha(attempt / "capture/evidence.jsonl"),
        "realized_observables": {},
    }
    result = physical_result(attempt, result)
    analysis = {
        "format": "worker-reverse-alternative-analysis", "case_id": case_id,
        "measurements": {"reverse_" + alternative: {
            "method": "analyze_original_reverse_region",
            "value": result["measured_values"],
            "sources": report["source_sha256"]}},
        "source_report": report, "source_hashes": report["source_sha256"],
        "physical_checks": result["physical_checks"],
        "legal_verdict_asserted": False,
    }
    write_result(attempt, result)
    output.write_text(json.dumps(analysis, indent=2, allow_nan=False) + "\n")
    return analysis


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)


if __name__ == "__main__":
    main()
