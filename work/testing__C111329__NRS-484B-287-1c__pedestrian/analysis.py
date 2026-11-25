"""Finalize saved C111329 crossing observations without a legal verdict.

The finalizer reads original acquisition files only. The fixture path uses the
same measurement functions but is labelled diagnostic in its provenance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_observation import CAMERAS, analyze_saved
from site_geometry import assess_site


def _required(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inputs(root: Path):
    packet_path = _required(root, "effective-site-packet.json")
    observation_path = _required(root, "original-site-observation.json")
    packet = json.loads(packet_path.read_text())
    observation = json.loads(observation_path.read_text())
    case_id = observation["case_id"]
    receipt = {"path": str(observation_path), "sha256": _sha(observation_path),
               "frame_count": observation["frame_count"], "case_id": case_id}
    site = assess_site(packet, require_operating=False)
    motion = analyze_saved(packet, receipt, expected_case_id=case_id, required_frames=900)
    return packet, observation, site, motion


def measure_between_site(root: Path) -> dict:
    _, _, site, _ = _inputs(root)
    paths = ["effective-site-packet.json", "original-site-observation.json"]
    return {"method": "measure_between_site",
            "sources": {name: _sha(_required(root, name)) for name in paths},
            "value": {"junction_ids": site["between_junction_ids"],
                      "station_fraction": site["crossing_station_fraction"],
                      "crosses_both_highway_banks": site["crosses_both_highway_banks"],
                      "source_sha256": site["source_sha256"]}}


def measure_original_crossing(root: Path) -> dict:
    _, _, site, motion = _inputs(root)
    paths = ["effective-site-packet.json", "original-site-observation.json"]
    return {"method": "measure_original_crossing",
            "sources": {name: _sha(_required(root, name)) for name in paths},
            "value": {"frame_count": motion["frame_count"],
                      "crossed_both_highway_banks": motion["crossed_both_highway_banks"],
                      "crossing_frame_range": motion["observed_crossing_frame_range"],
                      "marked_crosswalk_present": site["marked_crosswalk_present"],
                      "both_devices_operating_during_crossing": motion["both_devices_operating_during_crossing"]}}


def measure_official_context(root: Path) -> dict:
    _, _, site, _ = _inputs(root)
    paths = ["effective-site-packet.json", "original-site-observation.json"]
    return {"method": "measure_official_context",
            "sources": {name: _sha(_required(root, name)) for name in paths},
            "value": {"device_ids": site["device_ids"],
                      "source_sha256": site["source_sha256"]["devices"],
                      "legal_official_status": "undetermined",
                      "legal_adjacency": "undetermined"}}


def measure_exception_context(root: Path) -> dict:
    _, _, site, _ = _inputs(root)
    paths = ["effective-site-packet.json", "original-site-observation.json"]
    return {"method": "measure_exception_context",
            "sources": {name: _sha(_required(root, name)) for name in paths},
            "value": {"highway_source_sha256": site["source_sha256"]["highway"],
                      "nrs_484b_290_exception": "undetermined",
                      "legal_review_required": True}}


def _rows(root: Path, name: str) -> list[dict]:
    return [json.loads(line) for line in _required(root, name).read_text().splitlines() if line]


def analyze(root: Path, output: Path) -> dict:
    root, output = Path(root).resolve(), Path(output).resolve()
    packet, observation, site, motion = _inputs(root)
    config = json.loads(_required(root, "config.json").read_text())
    case_id = config["selected_case_id"]
    if observation["case_id"] != case_id:
        raise ValueError("saved original observation selects another exact case")
    marked = bool(config["case"]["case_id"].endswith("midblock_marked_operating"))
    operating = not case_id.endswith("midblock_unmarked_inactive")
    if site["marked_crosswalk_present"] is not marked or \
       motion["both_devices_operating_during_crossing"] is not operating:
        raise ValueError("saved original case distinction differs")
    frame_map = _rows(root, "video_frames.jsonl")
    trace = _rows(root, "trace.jsonl")
    samples = observation["frames"]
    if len(frame_map) != 900 or len(trace) != 900:
        raise ValueError("saved original frame map or trace incomplete")
    for index, (sample, mapped, body) in enumerate(zip(samples, frame_map, trace)):
        frame, time_s = sample["frame"], sample["time_s"]
        if mapped.get("video_frame") != index or mapped.get("carla_frame") != frame or \
           mapped.get("native_frame") != frame or abs(mapped.get("time_s", -1) - time_s) > 1e-6 or \
           body.get("frame") != frame or abs(body.get("time_s", -1) - time_s) > 1e-6 or \
           body.get("position_m") != sample["walker_xyz_m"]:
            raise ValueError("saved original frame/time/body join differs")
    for camera in CAMERAS:
        _required(root, camera + ".mkv")
    channels = root / "channels"
    channels.mkdir(exist_ok=False)
    description = config["case"]["recording_description"]
    evidence = []
    values = {
        "walker_crossing_route": lambda row: {"walker_xyz_m": row["walker_xyz_m"], "frame": row["frame"]},
        "device_operation": lambda row: row["devices"],
        "marking_and_junction_context": lambda row: {"site_source_sha256": site["source_sha256"],
                                                       "crossing_station_fraction": site["crossing_station_fraction"]},
    }
    for channel in description["channels"]:
        name = channel["name"]
        if name not in values:
            raise ValueError("unimplemented selected channel: " + name)
        relative = "channels/" + name + ".jsonl"
        with (root / relative).open("x") as stream:
            for row in samples:
                stream.write(json.dumps({"time_s": row["time_s"], "value": values[name](row)},
                                        separators=(",", ":"), allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": channel["unit"], "reference": relative})
    context = "channels/highway_and_exception_review.json"
    (root / context).write_text(json.dumps({"highway_and_exception_review": {
        "source_sha256": site["source_sha256"],
        "legal_adjacency": "undetermined", "legal_official_status": "undetermined",
        "nrs_484b_290_exception": "undetermined"}}, allow_nan=False) + "\n")
    evidence.append({"name": "highway_and_exception_review", "unit": "source", "reference": context})
    targets = [{"target": "source-bound between-junction crossing and exact case distinction",
        "requested": True, "measured": True, "method": "measure_original_crossing",
        "tolerance": 0, "matched": True, "physical_cause_confirmed": False,
        "cause_evidence": ["effective-site-packet.json", "original-site-observation.json"]}]
    native = {"case_id": case_id,
        "measured_values": {"site": site, "motion": motion}, "target_checks": targets,
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "Saved source measurements; independent physical review pending",
        "physical_failure_flags": [], "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in CAMERAS],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description, "recording_evidence": evidence,
        "realized_observables": {}}
    (root / "result.json").write_text(json.dumps(native, indent=2, allow_nan=False) + "\n")
    report = {"format": "worker-analysis-report", "case_id": case_id,
        "measurements": {"between_site": measure_between_site(root),
                         "original_crossing": measure_original_crossing(root),
                         "official_context": measure_official_context(root),
                         "exception_context": measure_exception_context(root)},
        "limitations": ["Legal adjacency, official device status and NRS 484B.290 exception require independent review."]}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    analyze(args.attempt, args.output)


if __name__ == "__main__":
    main()
