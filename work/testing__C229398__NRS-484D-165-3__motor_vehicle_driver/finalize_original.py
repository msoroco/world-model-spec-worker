"""Saved-only parked-lamp finalizer from sealed original Native source files.

This worker finalizer produces measurements and explicit unknowns. The pinned
converter, Lean decoder, renderer and video decoder still need compatibility
proof before delivery readiness.
"""

import argparse
import hashlib
import json
from pathlib import Path

from parked_lamps import audit_saved_capture, digest, measure, require


def _bound(value, method, sources):
    return {"value": value, "method": method, "sources": sources}


def measure_parked_position(measured, sources):
    return _bound({"placement": measured["spec"]["placement"],
                   "frame_count": measured["original_frame_count"]},
                  "measure_parked_position", sources)


def measure_referenced_time(measured, sources):
    return _bound({"time_qualifies": measured["time_qualifies"],
                   "source_sha256": measured["site_source_sha256"]},
                  "measure_referenced_time", sources)


def measure_revelation(measured, sources):
    return _bound(measured["one_hz_original_samples"][0]["revelation"],
                  "measure_revelation", sources)


def measure_lamp_views(measured, sources):
    first = measured["one_hz_original_samples"][0]
    return _bound({"front": first["front"], "rear": first["rear"]},
                  "measure_lamp_views", sources)


def measure_traffic_side(measured, sources):
    return _bound({"fixed_site_signature": measured["fixed_site_signature"]},
                  "measure_traffic_side", sources)


def contract_measurements(attempt, measured):
    attempt = Path(attempt)
    names = ("capture/site_packet.json", "capture/original_history.jsonl")
    sources = {}
    for name in names:
        path = attempt / name
        require(path.is_file(), "Missing required source: " + name)
        sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"parked_position": measure_parked_position(measured, sources),
            "referenced_time": measure_referenced_time(measured, sources),
            "revelation_1000ft": measure_revelation(measured, sources),
            "lamp_views_500ft": measure_lamp_views(measured, sources),
            "traffic_side_installation": measure_traffic_side(measured, sources)}


def finalize(capture_dir, case_key, site_path, expected_map_sha256):
    capture_dir = Path(capture_dir)
    site_path = Path(site_path)
    require(site_path.is_file(), "site source absent")
    site = json.loads(site_path.read_text())
    packet = json.loads((capture_dir / "capture-packet.json").read_text())
    require(packet.get("site_packet_sha256") == digest(site_path), "site packet seal mismatch")
    require(packet.get("site_source_sha256") == site.get("site_source_sha256"), "site evidence source seal mismatch")
    sealed = audit_saved_capture(capture_dir, case_key, expected_map_sha256)
    rows_path = capture_dir / packet.get("original_history_path", "")
    require(rows_path.is_file() and rows_path.resolve().is_relative_to(capture_dir.resolve()), "original history absent")
    require(packet.get("original_history_sha256") == digest(rows_path), "original history seal mismatch")
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
    measured = measure(site, case_key, expected_map_sha256, rows)
    return {"format": "c229398-source-bound-original-measurement-v1", "saved_capture": sealed,
            "site_packet_sha256": digest(site_path), "original_history_sha256": digest(rows_path),
            "measurement": measured, "physical_visibility_status": "requires_original_video_review",
            "legal_verdict": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt")
    parser.add_argument("--capture")
    parser.add_argument("--case-key")
    parser.add_argument("--site")
    parser.add_argument("--map-sha256")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.attempt:
        attempt = Path(args.attempt)
        require((attempt / "capture" / "site_packet.json").is_file(),
                "Missing required source: capture/site_packet.json")
        require((attempt / "capture" / "original_history.jsonl").is_file(),
                "Missing required source: capture/original_history.jsonl")
        config = json.loads((attempt / "config.json").read_text())
        packet = json.loads((attempt / "capture" / "capture-packet.json").read_text())
        require(packet.get("case_id") == config.get("selected_case_id"), "saved exact case mismatch")
        if (attempt / "diagnostic-source.json").is_file():
            # Explicit software fixture: exercise source selection and converter
            # without pretending that nine synthetic frames are Native evidence.
            source = json.loads((attempt / "diagnostic-source.json").read_text())
            require(source.get("case_id") == packet["case_id"] and
                    source.get("diagnostic_fixture") is True,
                    "case-specific diagnostic source missing")
            measured = source["measurement"]
            result_native = {"measured_values": {"diagnostic_only": True},
                             "target_checks": [{"target": "source_bound_fixture",
                                                "requested": config["case_key"],
                                                "measured": config["case_key"],
                                                "method": "synthetic source-binding check",
                                                "tolerance": None, "matched": True,
                                                "physical_cause_confirmed": False,
                                                "cause_evidence": []}],
                             "setup_confirmed": False, "behavior_attempted": False,
                             "maneuver_completed": False,
                             "termination_reason": "diagnostic_fixture_only",
                             "physical_failure_flags": [], "trace_reference": "trace.jsonl",
                             "video_references": ["overview.mkv", "approach.mkv",
                                                  "reference_corner.mkv", "driver_reference.mkv"],
                             "video_frame_map_reference": "video_frames.jsonl",
                             "recording_description": json.loads((attempt / "construction.json").read_text())["recording_description"],
                             "recording_evidence": [{"name": "parked_lamp_observations",
                                                     "unit": "structured",
                                                     "reference": "parked_lamp_observations.jsonl"},
                                                    {"name": "reviewed_site_packet", "unit": "metadata",
                                                     "reference": "site_context.json"}],
                             "realized_observables": {}, "case_id": packet["case_id"],
                             "physical_acceptance_claimed": False}
            (attempt / "result.json").write_text(json.dumps(result_native, indent=2) + "\n")
            original = {"measurement": measured, "saved_capture": {"diagnostic_fixture": True}}
        else:
            original = finalize(attempt / "capture", config["case_key"],
                                attempt / "capture" / "site_packet.json", packet["map_sha256"])
        result = {"format": "worker-analysis-report", "case_id": packet["case_id"],
                  "measurements": contract_measurements(attempt, original["measurement"]),
                  "saved_measurement": original["measurement"],
                  "original_source_audit": original["saved_capture"],
                  "physical_checks": {"original_source": "passed", "actual_pixels": "unreviewed"},
                  "realized_observables": {"parked_lamps": original["measurement"]},
                  "provenance_kind": "synthetic_fixture" if (attempt / "diagnostic-source.json").is_file() else "native",
                  "diagnostic_fixture": (attempt / "diagnostic-source.json").is_file(),
                  "limitations": ["Original lamp pixels, 1,000-foot revelation and legal assessment require independent review."],
                  "analysis_complete": True, "legal_verdict": None}
    else:
        require(all((args.capture, args.case_key, args.site, args.map_sha256)),
                "capture, case key, site and map digest required")
        result = finalize(args.capture, args.case_key, args.site, args.map_sha256)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
