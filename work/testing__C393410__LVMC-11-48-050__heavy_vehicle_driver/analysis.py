"""Saved-only original-source nighttime truck finalizer; no legal verdict."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from restriction_measure import load_review, measure, sha

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CHANNELS = ("ego_operation", "actual_unladen_weight", "local_civil_time",
            "residence_district", "street_designation", "written_permit")


def required(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def measure_weight(source: Path) -> dict:
    m = measure(source)
    return {key: m[key] for key in ("actual_unladen_weight_lb", "weight_strictly_exceeds_8000")}


def measure_time(source: Path) -> dict:
    m = measure(source)
    return {key: m[key] for key in ("local_civil_start", "local_civil_start_hhmm",
                                    "clock_uncertainty_s", "legal_time_endpoint_judgment")}


def measure_street(source: Path) -> dict:
    m = measure(source)
    return {key: m[key] for key in ("district_reviewed_as", "traveled_street_designation")}


def measure_operation(source: Path) -> dict:
    m = measure(source)
    return {key: m[key] for key in ("sample_count", "first_native_frame", "last_native_frame")}


def measure_route(source: Path) -> dict:
    return {"traveled_street_designation": measure(source)["traveled_street_designation"]}


def measure_district(source: Path) -> dict:
    return {"district_reviewed_as": measure(source)["district_reviewed_as"]}


def measure_permit(source: Path) -> dict:
    m = measure(source)
    return {key: m[key] for key in ("permit_review_status", "permit_conditions",
                                    "legal_permit_effect_judgment")}


def measure_application(source: Path) -> dict:
    packet = json.loads(Path(source).read_text())
    return {"written_application": packet["permit"].get("written_application"),
            "issued_written_permit": packet["permit"].get("issued_written_permit")}


def measure_vehicle_scope(source: Path) -> dict:
    packet = json.loads(Path(source).read_text())
    return {"vehicle_identity": packet["vehicle"]["identity"],
            "authorized_vehicle_identity": packet["permit"].get("authorized_vehicle_identity"),
            "scope_judgment": "unresolved"}


def measure_conditions(source: Path) -> dict:
    packet = json.loads(Path(source).read_text())
    return {"conditions": packet["permit"].get("conditions", []),
            "permit_review_status": packet["permit"]["status"],
            "conditions_judgment": "unresolved"}


def analyze(attempt: Path, output: Path) -> dict:
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    config = json.loads(required(attempt, "config.json").read_text())
    case_id = config["selected_case_id"]
    source = required(attempt, "original-night-truck-observations.json")
    packet = json.loads(source.read_text())
    receipt = json.loads(required(attempt, "original-night-truck-receipt.json").read_text())
    if (packet.get("case_id") != case_id or receipt.get("case_id") != case_id
            or receipt.get("source_sha256") != sha(source) or receipt.get("fps") != 20):
        raise ValueError("Original night truck receipt identity or source hash differs")
    review_path = required(attempt, "reviewed-night-truck.json")
    review = load_review(review_path, attempt / "reviewed-sources", case_id,
                         diagnostic=bool(packet.get("diagnostic_fixture")))
    if receipt.get("review_sha256") != sha(review_path) or packet.get("review_source_sha256") != sha(review_path):
        raise ValueError("Original night truck review source differs")
    for key in ("site", "vehicle", "civil_clock", "permit", "itinerary"):
        if packet.get(key) != review.get(key):
            raise ValueError("Original night truck observation context differs: " + key)
    measurement = measure(source)
    frames = packet["frames"]
    if receipt.get("frame_count") != len(frames):
        raise ValueError("Original night truck frame count differs")
    frame_map = rows(required(attempt, "video_frames.jsonl"))
    trace = rows(required(attempt, "trace.jsonl"))
    if packet.get("diagnostic_fixture") is False and packet.get("original_trace_id") != "Native:" + sha(attempt / "trace.jsonl"):
        raise ValueError("Original night truck trace source differs")
    if len(frames) != len(frame_map) or len(frames) != len(trace):
        raise ValueError("Original night truck streams differ")
    for index, (frame, mapped, row) in enumerate(zip(frames, frame_map, trace)):
        if (mapped.get("video_frame") != index or frame.get("frame") != mapped.get("carla_frame")
                or frame["frame"] != mapped.get("native_frame") or row.get("frame") != frame["frame"]
                or abs(frame["time_s"] - mapped.get("time_s", -1)) > 1e-4
                or abs(frame["time_s"] - row.get("time_s", -1)) > 1e-4):
            raise ValueError("Original night truck frame/time join differs")
    for camera in CAMERAS:
        required(attempt, camera + ".mkv")
    description = config["case"]["recording_description"]
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    values = {
        "ego_operation": lambda frame: {"ego_actor_id": frame["ego_actor_id"],
            "road_id": frame["road_id"], "position_xy_m": frame["position_xy_m"]},
        "actual_unladen_weight": lambda frame: {"lb": packet["vehicle"]["unladen_weight_lb"],
            "vehicle_identity": packet["vehicle"]["identity"], "source_sha256": packet["vehicle"]["weight_source_sha256"]},
        "local_civil_time": lambda frame: {"start_utc": packet["civil_clock"]["start_utc"],
            "timezone": packet["civil_clock"]["timezone"], "time_s": frame["time_s"],
            "clock_source_sha256": packet["civil_clock"]["clock_source_sha256"]},
        "residence_district": lambda frame: {"district": packet["site"]["district"],
            "frontage_reviewed": packet["site"]["frontage_reviewed"],
            "business_exclusion_reviewed": packet["site"]["business_exclusion_reviewed"]},
        "street_designation": lambda frame: {"road_id": frame["road_id"],
            "designation": frame["street_designation"],
            "source_sha256": packet["site"]["traveled_street"]["designation_source_sha256"]},
        "written_permit": lambda frame: {"status": packet["permit"]["status"],
            "issued_written_permit": packet["permit"].get("issued_written_permit"),
            "administrative_source_sha256": packet["permit"]["administrative_source_sha256"]}}
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        if name not in values:
            raise ValueError("Unimplemented night truck channel " + name)
        reference = "channels/" + name + ".jsonl"
        with (attempt / reference).open("x") as stream:
            for frame in frames:
                stream.write(json.dumps({"time_s": frame["time_s"], "value": values[name](frame)},
                                        separators=(",", ":")) + "\n")
        evidence.append({"name": name, "unit": channel["unit"], "reference": reference})
    context = "channels/reviewed_night_truck_site.json"
    (attempt / context).write_text(json.dumps({"reviewed_night_truck_site": {
        "review_source_sha256": sha(review_path), "legal_judgment": "unresolved"}}) + "\n")
    evidence.append({"name": "reviewed_night_truck_site", "unit": "source", "reference": context})
    native = {"case_id": case_id, "measured_values": {"night_truck": measurement},
        "target_checks": [{"target": "source-bound nighttime heavy-truck operation", "requested": True,
            "measured": True, "method": "measure", "tolerance": 0, "matched": True,
            "physical_cause_confirmed": False, "cause_evidence": ["original-night-truck-observations.json"]}],
        "setup_confirmed": False, "behavior_attempted": False, "maneuver_completed": False,
        "termination_reason": "Saved night truck measurement; physical and legal review pending",
        "physical_failure_flags": [], "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in CAMERAS],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description, "recording_evidence": evidence,
        "realized_observables": {}}
    (attempt / "result.json").write_text(json.dumps(native, indent=2, allow_nan=False) + "\n")
    methods = (("weight", measure_weight), ("operation", measure_operation),
               ("route", measure_route), ("district", measure_district),
               ("time", measure_time), ("application", measure_application),
               ("vehicle_scope", measure_vehicle_scope), ("conditions", measure_conditions))
    report = {"format": "worker-analysis-report", "case_id": case_id,
        "measurements": {name: {"method": method.__name__,
            "sources": {"original-night-truck-observations.json": sha(source),
                        "original-night-truck-receipt.json": sha(attempt / "original-night-truck-receipt.json"),
                        "reviewed-night-truck.json": sha(review_path)},
            "value": method(source)} for name, method in methods},
        "limitations": ["Original municipal/administrative sources and Native motion need independent review; no legal endpoint or permit verdict is claimed."]}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    analyze(args.attempt, args.output)


if __name__ == "__main__":
    main()
