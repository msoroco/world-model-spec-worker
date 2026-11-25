"""Finalize one saved pedestrian bypass and report source-bound observations.

The diagnostic flag is explicit. Production requires an original saved packet;
neither path asserts physical completion or a legal conclusion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from saved_finalizer import build_result
from saved_measurement import REQUIRED


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analyze(attempt: Path, output: Path, *, diagnostic: bool = False) -> dict:
    """Write a Native result and a separate report without changing acquisition."""
    from worker_exchange.native_output import write_result

    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    if output.parent != attempt or output.name != "analysis-report.json":
        raise ValueError("analysis report must be local to saved attempt")
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("prior result or analysis report exists")
    config = json.loads((attempt / "config.json").read_text())
    case_id = config["selected_case_id"]
    diagnostic = diagnostic or config.get("diagnostic_only") is True
    packet = attempt / "source-packet.json"
    retained_packet = attempt / "pedestrian-packet.json"
    if retained_packet.is_file():
        if packet.is_file() and packet.read_bytes() != retained_packet.read_bytes():
            raise ValueError("saved pedestrian packet differs from retained acquisition")
        if not packet.exists():
            packet.write_bytes(retained_packet.read_bytes())
    for name in REQUIRED:
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    result = build_result(attempt, case_id, diagnostic=diagnostic, decode_media=True)
    measured = result["measured_values"]
    if (attempt / "trace.jsonl").is_file():
        result["trace_reference"] = "trace.jsonl"
    if isinstance(result["recording_description"], dict):
        channels = attempt / "channels"
        if channels.exists():
            raise ValueError("prior derived channel output exists")
        channels.mkdir()
        frames = [json.loads(line) for line in (attempt / "video_frames.jsonl").read_text().splitlines()]
        bodies = [json.loads(line) for line in (attempt / "pedestrian_history.jsonl").read_text().splitlines()]
        traffic = [json.loads(line) for line in (attempt / "traffic_history.jsonl").read_text().splitlines()]
        if not (len(frames) == len(bodies) == len(traffic)):
            raise ValueError("derived channel source lengths differ")
        body_rows, distance_rows = [], []
        for frame, body, vehicle in zip(frames, bodies, traffic):
            vertices = body["body_vertices_world_m"]
            center = {"x": (min(v[0] for v in vertices) + max(v[0] for v in vertices)) / 2,
                      "y": (min(v[1] for v in vertices) + max(v[1] for v in vertices)) / 2}
            body_rows.append({"time_s": frame["time_s"], "value": center})
            distance_rows.append({"time_s": frame["time_s"],
                                  "value": vehicle["nearest_traffic_distance_m"]})
        (channels / "pedestrian_body_center_xy_m.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in body_rows))
        (channels / "nearest_traffic_distance_m.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in distance_rows))
        (channels / "source_provenance.json").write_text(json.dumps({
            "source_provenance": {"packet_sha256": _sha(packet),
                                  "site_survey_sha256": _sha(attempt / "site-survey.json"),
                                  "diagnostic_fixture": diagnostic}}, indent=2) + "\n")
        result["recording_evidence"] = [
            {"name": "pedestrian_body_center_xy_m", "unit": "structured",
             "reference": "channels/pedestrian_body_center_xy_m.jsonl"},
            {"name": "nearest_traffic_distance_m", "unit": "m",
             "reference": "channels/nearest_traffic_distance_m.jsonl"},
            {"name": "source_provenance", "unit": "metadata",
             "reference": "channels/source_provenance.json"},
        ]
        result["realized_observables"] = {}
    report = {
        "format": "worker-pedestrian-bypass-analysis",
        "case_id": case_id,
        "diagnostic_fixture": result["diagnostic_fixture"],
        "measurements": {
            "pedestrian_direction": {
                "method": "measure_direction",
                "value": measure_direction(measured),
                "sources": {name: _sha(attempt / name) for name in
                            ("site-survey.json", "pedestrian_history.jsonl")},
            },
            "designated_lane_used": {
                "method": "measure_lane_use",
                "value": measure_lane_use(measured),
                "sources": {name: _sha(attempt / name) for name in
                            ("site-survey.json", "pedestrian_history.jsonl",
                             "obstruction_history.jsonl")},
            },
            "first_sidewalk_return_frame": {
                "method": "measure_return",
                "value": measure_return(measured),
                "sources": {name: _sha(attempt / name) for name in
                            ("site-survey.json", "video_frames.jsonl",
                             "pedestrian_history.jsonl")},
            },
            "nearest_traffic_distance_m": {
                "method": "measure_traffic_distance",
                "value": measure_traffic_distance(measured),
                "sources": {"traffic_history.jsonl": _sha(attempt / "traffic_history.jsonl")},
            },
            "sidewalk_obstruction_kind": {
                "method": "measure_obstruction_kind",
                "value": measure_obstruction_kind(measured),
                "sources": {name: _sha(attempt / name) for name in
                            ("site-survey.json", "obstruction_history.jsonl")},
            },
            "intervening_barrier_present": {
                "method": "measure_intervening_barrier",
                "value": measure_intervening_barrier(measured),
                "sources": {name: _sha(attempt / name) for name in
                            ("site-survey.json", "obstruction_history.jsonl")},
            },
            "lateral_distance_to_sidewalk_edge_m": {
                "method": "measure_lateral_distance",
                "value": measure_lateral_distance(measured),
                "sources": {name: _sha(attempt / name) for name in
                            ("site-survey.json", "pedestrian_history.jsonl")},
            },
        },
        "physical_acceptance": "not_assessed",
        "legal_judgment": "unresolved",
    }
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


def measure_direction(observations: dict) -> int:
    """Return observed signed longitudinal travel direction."""
    return observations["pedestrian_direction"]


def measure_lane_use(observations: dict) -> bool:
    """Return measured designated-lane occupancy."""
    return observations["designated_lane_used"]


def measure_return(observations: dict) -> int:
    """Return first sidewalk frame after the highway bypass."""
    return observations["first_sidewalk_return_frame"]


def measure_traffic_distance(observations: dict) -> list[float]:
    """Return per-frame distance context without turning it into due care."""
    return observations["nearest_traffic_distance_m"]


def measure_obstruction_kind(observations: dict) -> str:
    """Return the observed sidewalk obstruction type."""
    return observations["sidewalk_obstruction_kind"]


def measure_intervening_barrier(observations: dict) -> bool:
    """Return whether the source measured an intervening physical barrier."""
    return observations["intervening_barrier_present"]


def measure_lateral_distance(observations: dict) -> list[float]:
    """Return every highway frame's distance from the surveyed sidewalk edge."""
    return observations["lateral_distance_to_sidewalk_edge_m"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    report = analyze(args.attempt, args.output, diagnostic=args.diagnostic)
    print(json.dumps({"case_id": report["case_id"],
                      "diagnostic_fixture": report["diagnostic_fixture"]}))


if __name__ == "__main__":
    main()
