"""Saved-only finalization for original C111250 Native captures."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_selected import SOURCES, measure, rows


VIDEOS = ("overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_original_native_cycle_lane(attempt, diagnostic=False):
    return measure(attempt, allow_diagnostic=diagnostic)


def measure_subsection3_context(attempt):
    """Retain original circumstance readback without inferring a legal exception."""
    return json.loads((Path(attempt) / "subsection3-context.json").read_text())


def finalize(attempt, output):
    attempt = Path(attempt); output = Path(output)
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Retain prior analysis; use a fresh attempt")
    for name in (*SOURCES, *VIDEOS, "config.json", "construction.json"):
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    construction = json.loads((attempt / "construction.json").read_text())
    fixture_manifest = attempt / "capture/manifest.json"
    diagnostic = fixture_manifest.is_file() and json.loads(fixture_manifest.read_text()).get("synthetic_diagnostic") is True
    if config["case_id"] != construction["case_id"]:
        raise ValueError("Exact original case identity differs")
    if not diagnostic:
        report_path = attempt / "native-capture-report.json"
        if not report_path.is_file():
            raise ValueError("Missing required source: native-capture-report.json")
        report = json.loads(report_path.read_text())
        if report.get("case_id") != config["case_id"] or report.get("frames") != 600 or \
           report.get("error") is not None or report.get("restoration", {}).get("restored") is not True:
            raise ValueError("Native acquisition or world restoration incomplete")
    value = measure_original_native_cycle_lane(attempt, diagnostic=diagnostic)
    if (value["source_kind"] == "synthetic_cpu_diagnostic") != diagnostic:
        raise ValueError("Fixture/source provenance differs")
    expected_overlap = config["case_suffix"] in ("outside_cycle_lane", "within_cycle_lane")
    matched = expected_overlap and value["cycle_lane_intersection_overlap_frames"] > 0
    channel_folder = attempt / "channels"
    channel_folder.mkdir()
    channel_evidence = []
    bodies = rows(attempt / "body-history.jsonl")
    for name in ("vehicle_body", "cycle_facility", "st.bicycle_lane_or_path",
                 "rel.occupies", "st.intersection", "drv.entering_intersection",
                 "drv.in_intersection", "kin.velocity"):
        path = channel_folder / (name + ".jsonl")
        with path.open("x") as stream:
            for body in bodies:
                observed = (body["body_xy_m"] if name == "vehicle_body" else
                            [3.5, 5.5] if name in ("cycle_facility", "st.bicycle_lane_or_path") else
                            body["speed_mps"] if name == "kin.velocity" else
                            body["body_xy_m"])
                stream.write(json.dumps({"time_s": body["time_s"], "value": observed},
                                        allow_nan=False) + "\n")
        channel_evidence.append({"name": name, "unit": "structured",
                                 "reference": "channels/" + path.name,
                                 "sha256": sha(path)})
    analysis = {"format": "worker-analysis-report", "case_id": config["case_id"],
                "measurements": {"cycle_lane_intersection_measurement": {
                    "method": "measure_original_native_cycle_lane", "value": value,
                    "sources": value["source_sha256"]},
                    "subsection3_qualifier_context": {
                        "method": "measure_subsection3_context",
                        "value": measure_subsection3_context(attempt),
                        "sources": {name: sha(attempt / name) for name in
                                    ("facility-context.json", "subsection3-context.json")}}},
                "source_complete": True, "diagnostic_fixture": diagnostic,
                "physical_or_legal_acceptance": False}
    channel_evidence.extend([
        {"name": "native_facility_readback", "unit": "structured",
         "reference": "facility-context.json", "sha256": sha(attempt / "facility-context.json")},
        {"name": "subsection3_conflict_context", "unit": "structured",
         "reference": "subsection3-context.json", "sha256": sha(attempt / "subsection3-context.json")}])
    result = {"case_id": config["case_id"], "measured_values": value,
              "target_checks": [{"target": "original body occupancy in authored bicycle facility at intersection",
                  "requested": expected_overlap,
                  "measured": value["cycle_lane_intersection_overlap_frames"] > 0,
                  "method": "measure_original_native_cycle_lane", "tolerance": 0,
                  "matched": matched, "physical_cause_confirmed": False,
                  "cause_evidence": list(SOURCES)}],
              "setup_confirmed": False, "behavior_attempted": matched,
              "maneuver_completed": False,
              "termination_reason": "Original 600-frame Native capture; independent physical review pending",
              "physical_failure_flags": ["Official facility designation, subsection 3 legal circumstance and full pixels require independent review"],
              "trace_reference": "trace.jsonl", "video_references": list(VIDEOS),
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": construction["recording_description"],
              "recording_evidence": channel_evidence,
              "realized_observables": {},
              "provenance_kind": "synthetic_local_diagnostic" if diagnostic else "original_native_capture", "accepted": False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    with output.open("x") as stream:
        json.dump(analysis, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return analysis


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
