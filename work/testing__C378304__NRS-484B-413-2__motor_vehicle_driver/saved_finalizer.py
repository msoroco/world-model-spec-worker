"""Saved-only C378304 right-turn measurements from retained Native sources."""

import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
REPO = FOLDER.parents[1]
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from turn_signal_measurements import analyze

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def measure_continuous_right_signal_distance(report):
    return report["turn_onset"]["continuous_right_signal_distance_m"]


def source_district_boundary(report):
    return {"district_type": report["district_type"],
            "required_distance_m": report["required_distance_m"],
            "freight_loading_zone_source": report["freight_loading_zone_source"]}


def measure_right_turn_onset(report):
    return {"frame": report["turn_onset"]["frame"],
            "continuous_signal_meets_boundary": report["observed_continuous_distance_meets_boundary"],
            "weather_exception": report["weather_exception"]}


def finalize_saved(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / "result.json").exists() or (attempt / "channels").exists():
        raise ValueError("Retain prior finalization; choose a fresh saved version")
    required = ("config.json", "drive_history.jsonl", "route_context.json",
                "freight-zone-site-source.txt", "video_frames.jsonl", "trace.jsonl",
                "capture/evidence.jsonl", *(name + ".mkv" for name in CAMERAS))
    for name in required:
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    case = config.get("selected_case_id")
    if (config.get("cell_id") != "C378304" or config.get("law_id") != "NRS-484B-413-2"
            or not str(case).startswith("testing__C378304__NRS-484B-413-2__motor_vehicle_driver__")
            or not config.get("recording_description", {}).get("channels")):
        raise ValueError("Wrong exact C378304 saved capture identity")
    report = analyze(attempt)
    history = rows(attempt / "drive_history.jsonl")
    mapping = rows(attempt / "video_frames.jsonl")
    trace = rows(attempt / "trace.jsonl")
    if (len(history) != len(mapping) or len(trace) != len(mapping)
            or any(source.get("frame") != frame.get("carla_frame")
                   or source.get("time_s") != frame.get("time_s")
                   for source, frame in zip(trace, mapping))):
        raise ValueError("Original trace/video frame join failed")
    values = {
        "ego_speed": ("m/s", lambda row: row["ego_speed_mps"]),
        "ego_heading": ("deg", lambda row: row["ego_heading_deg"]),
        "ego_road_id": ("id", lambda row: row["native_road_id"]),
        "ego_turn_indicator": ("device state", lambda row: {
            "reported_mask": row["ego_light_mask"],
            "reported_device_state": "right" if row["right_indicator"] else "off"}),
    }
    derived = {name: [getter(row) for row in history]
               for name, (_, getter) in values.items()}
    path_distance = [0.0]
    for before, after in zip(history, history[1:]):
        path_distance.append(path_distance[-1] + math.dist(
            before["ego_position_xy_m"], after["ego_position_xy_m"]))
    derived["path_distance"] = path_distance
    values["path_distance"] = ("m", None)
    evidence_root = attempt / "evidence"
    evidence_root.mkdir()
    for name in ("config.json", "drive_history.jsonl", "route_context.json",
                 "freight-zone-site-source.txt", "video_frames.jsonl", "trace.jsonl"):
        shutil.copyfile(attempt / name, evidence_root / name)
    shutil.copytree(attempt / "capture", evidence_root / "capture", dirs_exist_ok=True)
    channels = attempt / "channels"
    channels.mkdir()
    evidence = []
    for name, (unit, _) in values.items():
        reference = "channels/" + name + ".jsonl"
        with (attempt / reference).open("x") as stream:
            for row, value in zip(history, derived[name]):
                stream.write(json.dumps({"time_s": row["time_s"],
                                         "original_frame": row["frame"],
                                         "value": value}, allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": unit, "reference": reference})
    evidence.append({"name": "freight_zone_site", "unit": "source document",
                     "reference": "contexts/freight_zone_site.json"})
    context = json.loads((attempt / "route_context.json").read_text())
    contextual = {
        "freight_zone_site": {"source": "freight-zone-site-source.txt",
                              "sha256": sha(attempt / "freight-zone-site-source.txt")},
        "district": {"type": context["district_type"],
                     "source": context["district_source"]},
        "weather": context["native_weather_readback"],
    }
    context_root = attempt / "contexts"
    context_root.mkdir()
    for name, value in contextual.items():
        (context_root / (name + ".json")).write_text(json.dumps({name: value}) + "\n")
    evidence.extend({"name": name,
                     "unit": "legal region class" if name == "district" else "CARLA weather scale",
                     "reference": "contexts/" + name + ".json"}
                    for name in ("district", "weather"))
    checksums = {"evidence/" + path.relative_to(evidence_root).as_posix(): sha(path)
                 for path in evidence_root.rglob("*") if path.is_file()}
    (attempt / "evidence-checksums.json").write_text(json.dumps(checksums, sort_keys=True) + "\n")
    from worker_exchange.native_output import physical_result, write_result
    observed = report["observed_continuous_distance_meets_boundary"]
    result = {"case_id": case,
              "measured_values": {
                  "continuous_right_signal_distance_m": report["turn_onset"]["continuous_right_signal_distance_m"],
                  "district_boundary_m": report["required_distance_m"],
                  "turn_onset_frame": report["turn_onset"]["frame"]},
              "target_checks": [{"target": "continuous_right_signal_boundary",
                                 "requested": True, "measured": observed,
                                 "method": "original Native light-mask readback and sampled path before measured right-turn onset",
                                 "tolerance": 0.0, "matched": observed,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": list(report["sources"])}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "Saved source assessment pending",
              "physical_failure_flags": ["Native indicator pixels and district class require independent review"],
              "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in CAMERAS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": config["recording_description"],
              "recording_evidence": evidence,
              "source_evidence_hashes": report["sources"],
              "capture_evidence_sha256": sha(attempt / "capture/evidence.jsonl"),
              "realized_observables": {}}
    result = physical_result(attempt, result)
    write_result(attempt, result)
    measurement_specs = (
        ("continuous_right_signal_distance_m", measure_continuous_right_signal_distance,
         ("drive_history.jsonl", "video_frames.jsonl", "route_context.json")),
        ("district_boundary_source", source_district_boundary,
         ("route_context.json", "freight-zone-site-source.txt")),
        ("right_turn_onset_and_weather", measure_right_turn_onset,
         ("drive_history.jsonl", "video_frames.jsonl", "route_context.json")),
    )
    measurements = {key: {"method": method.__name__, "value": method(report),
                          "sources": {name: sha(attempt / name) for name in sources}}
                    for key, method, sources in measurement_specs}
    analysis = {"format": "worker-right-turn-signal-analysis", "case_id": case,
                "source_report": report, "source_hashes": report["sources"],
                "measurements": measurements,
                "physical_checks": result["physical_checks"],
                "realized_observables": result["realized_observables"],
                "legal_verdict_asserted": False, "physical_acceptance_claimed": False}
    output.write_text(json.dumps(analysis, indent=2, allow_nan=False) + "\n")
    return analysis


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    finalize_saved(args.attempt, args.output)
