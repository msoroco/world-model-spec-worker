"""Saved-only parking-side measurement with explicit source-role gates."""
import argparse
import hashlib
import json
from pathlib import Path

from one_way_saved_measure import CAMERAS, measure_original
from source_review import REQUIRED, reviewed_context

ASSIGNMENT = "training__C135709__NRS-484B-493__motor_vehicle_driver"
BASE_SOURCES = ("vehicle-pose.jsonl", "video_frames.jsonl", "road-context.json", "road.xodr")
CHANNELS = ("vehicle_footprint", "notice_and_street_context", "dev.regulatory_sign",
            "dev.governs", "st.one_way_roadway", "st.lane_direction",
            "drv.standing_or_parked", "rel.occupies")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def analyze(attempt):
    attempt = Path(attempt)
    for name in (*BASE_SOURCES, "config.json", *(c + ".mkv" for c in CAMERAS)):
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    config = read(attempt / "config.json")
    case = config.get("case_id")
    if (case not in (ASSIGNMENT + "__controlled_1", ASSIGNMENT + "__controlled_2") or
            config.get("selected_case_id") != case or config.get("law_id") != "NRS-484B-493" or
            config.get("cell_id") != "C135709" or config.get("rate_hz") != 20 or
            config.get("duration_s") != 30):
        raise ValueError("Exact saved case contract differs")
    provenance_path = attempt / "acquisition-provenance.json"
    diagnostic = (provenance_path.is_file() and
                  read(provenance_path).get("provenance_kind") == "synthetic_fixture")
    context = reviewed_context(attempt, diagnostic=diagnostic)
    raw_context = json.dumps(context, sort_keys=True, separators=(",", ":")).encode()
    measurement = measure_original((attempt / "vehicle-pose.jsonl").read_bytes(),
                                   (attempt / "video_frames.jsonl").read_bytes(),
                                   raw_context, (attempt / "road.xodr").read_bytes())
    frames = rows(attempt / "video_frames.jsonl")
    poses = rows(attempt / "vehicle-pose.jsonl")
    if len(frames) != 600 or len(poses) != 600:
        raise ValueError("Incomplete original source frames")
    source_names = list(BASE_SOURCES)
    for name in REQUIRED:
        source_names.extend(("authority-review/" + name + ".json",
                             "authority-review/" + name + ".source.txt"))
    return {"case_id": case, "config": config, "context": context,
            "diagnostic_fixture": diagnostic, "measurement": measurement,
            "frames": frames, "poses": poses,
            "source_sha256": {name: sha(attempt / name) for name in source_names},
            "video_sha256": {c + ".mkv": sha(attempt / (c + ".mkv")) for c in CAMERAS}}


def measure_notice_context(value):
    return {"value": {"one_way_designation_reviewed": True,
                      "official_erected_notice_reviewed": True,
                      "source_role_count": len(value["context"]["reviewed_source_hashes"]),
                      "legal_applicability_result": None},
            "method": "measure_notice_context",
            "sources": {name: value["source_sha256"][name] for name in
                        ("authority-review/device-authority.json",
                         "authority-review/one-way-designation.json", "road.xodr")}}


def measure_stationary_side(value):
    measurement = value["measurement"]
    return {"value": {"fully_left_stationary_frames": len(measurement["fully_left_governed_frames"]),
                      "fully_right_stationary_frames": len(measurement["fully_right_governed_frames"]),
                      "standing_or_parking_legal_classification": None},
            "method": "measure_stationary_side",
            "sources": {name: value["source_sha256"][name] for name in
                        ("vehicle-pose.jsonl", "video_frames.jsonl", "road-context.json")}}


def finalize(attempt, output):
    from worker_exchange.native_output import write_result
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Retain prior saved analysis/result")
    value = analyze(attempt)
    measured = value["measurement"]
    frames, poses = value["frames"], value["poses"]
    channels = attempt / "channels"
    channels.mkdir()
    left, right = set(measured["fully_left_governed_frames"]), set(measured["fully_right_governed_frames"])
    stationary = set(measured["stationary_frames"])
    for name in CHANNELS:
        with (channels / (name + ".jsonl")).open("x") as stream:
            for i, (frame, pose) in enumerate(zip(frames, poses)):
                if name == "vehicle_footprint":
                    item = {"corners_xy_m": pose["footprint_corners_xy_m"],
                            "speed_mps": pose["speed_mps"]}
                elif name == "notice_and_street_context":
                    item = {"source_hashes": value["context"]["reviewed_source_hashes"]}
                elif name == "dev.regulatory_sign":
                    item = {"device_id": value["context"]["device_id"],
                            "notice_content_source_reviewed": True}
                elif name == "dev.governs":
                    item = {"governed_road_id": value["context"]["device_governs_road_id"],
                            "extent_m": value["context"]["governed_longitudinal_extent_m"]}
                elif name == "st.one_way_roadway":
                    item = {"road_id": value["context"]["road_id"],
                            "designation_source_reviewed": True}
                elif name == "st.lane_direction":
                    item = {"permitted_direction_xy": value["context"]["permitted_direction_xy"]}
                elif name == "drv.standing_or_parked":
                    item = {"stationary_diagnostic": i in stationary,
                            "legal_purpose_classified": False}
                else:
                    item = {"fully_left_governed": i in left,
                            "fully_right_governed": i in right}
                stream.write(json.dumps({"time_s": frame["time_s"], "value": item}) + "\n")
    requested = value["config"]["parking_side"]
    matched = bool(left if requested == "left" else right)
    result = {"case_id": value["case_id"],
        "measured_values": {"stationary_side_diagnostic": {
            "fully_left_frames": len(left), "fully_right_frames": len(right),
            "source_hashes": value["source_sha256"], "legal_result": None}},
        "target_checks": [{"target": "source-observed stationary footprint side",
            "requested": requested, "measured": "left" if left else "right" if right else "unresolved",
            "method": "saved footprint projection on sourced one-way street centerline",
            "tolerance": 0, "matched": matched, "physical_cause_confirmed": False,
            "cause_evidence": list(value["source_sha256"])}],
        "setup_confirmed": False, "behavior_attempted": True, "maneuver_completed": False,
        "termination_reason": "Saved factual side measured; source authority and legal standing/parking need original review",
        "physical_failure_flags": ["original_notice_pixels_and_purpose_unreviewed"],
        "trace_reference": "trace.jsonl", "video_references": [c + ".mkv" for c in CAMERAS],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": value["config"]["recording_description"],
        "recording_evidence": [{"name": name, "unit": "structured",
            "reference": "channels/" + name + ".jsonl"} for name in CHANNELS],
        "realized_observables": {"stationary_side_frame_count": {"value": len(left) if requested == "left" else len(right),
            "unit": "frames", "method": "original footprint and speed projection",
            "time_window": "600 original frames", "statistic": "count",
            "reference": "channels/rel.occupies.jsonl"}},
        "accepted": False, "legal_verdict_claimed": False}
    write_result(attempt, result)
    report = {"format": "c135709-saved-side-measurements-v1", "case_id": value["case_id"],
              "measurements": {"notice_context": measure_notice_context(value),
                               "stationary_side": measure_stationary_side(value)},
              "diagnostic": {"source_sha256": value["source_sha256"],
                             "video_sha256": value["video_sha256"],
                             "diagnostic_fixture": value["diagnostic_fixture"],
                             "left_frames": len(left), "right_frames": len(right)},
              "physical_acceptance_claimed": False, "legal_verdict_claimed": False}
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
