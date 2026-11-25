"""Saved-only NRS 484B.603(1) approach measurement contract processor."""
from __future__ import annotations
import math

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
import xml.etree.ElementTree as ET

from measure_approach import measure


def _required(folder: Path, name: str) -> Path:
    path = folder / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure_intersection_approach(rows: list[dict], relation: dict,
                                  road: ET.Element) -> dict:
    if road.tag != "OpenDRIVE" or len(road.findall("road")) != 6:
        raise ValueError("Saved intersection map differs")
    other_start = rows[0]["other_position_m"]
    other_end = rows[-1]["other_position_m"]
    return {"declared_actor_role": rows[0]["ego_role"],
            "frames": relation["frames"],
            "approach_start_mph": relation["approach_start_mph"],
            "preentry_mph": relation["preentry_mph"],
            "crossing_peak_mph": relation["crossing_peak_mph"],
            "measured_decrease_mph": relation["decrease_mph"],
            "measured_relation": relation["measured_relation"],
            "measured_travel_direction_y": relation["measured_travel_direction_y"],
            "other_vehicle_displacement_m": round(abs(other_end[0]-other_start[0]), 3),
            "authored_road_count": len(road.findall("road")),
            "engineering_surrogate_thresholds_mph": relation["surrogate_thresholds_mph"],
            "reduction_necessity_legally_verified": False,
            "physical_hazard_observed": False}



def measure_curve_approach(folder: Path, value: dict) -> dict:
    import xml.etree.ElementTree as ET
    source = _rows(folder, "native_samples.jsonl")
    context = json.loads(_required(folder, "context.json").read_text())
    road = ET.fromstring(_required(folder, "road.xodr").read_text())
    first = next((r for r in road.findall("road") if r.get("id") == "1"), None)
    offsets = [] if first is None else first.findall("lanes/laneOffset")
    stations = {int(float(x.get("s", -1))) for x in offsets}
    if not context.get("curve_design") or not {100, 145, 190} <= stations or len(source) != 600:
        raise ValueError("Missing source-bound curve geometry")
    x = [row["ego_position_m"][0] for row in source]
    excursion = max(x) - min(x)
    if excursion < .6:
        raise ValueError("Original Native ego path did not traverse curve")
    return dict(value, measured_lateral_excursion_m=excursion,
                road_curve_stations_m=[100, 145, 190, 233],
                curve_necessity_legally_verified=False)


def finalize(folder: Path, contract: dict, expected_source_sha256: str) -> dict:
    folder = Path(folder)
    rows_path = _required(folder, "native_samples.jsonl")
    road_path = _required(folder, "road.xodr")
    relation = measure(rows_path, expected_source_sha256)
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
    road = ET.parse(road_path).getroot()
    value = measure_curve_approach(folder, measure_intersection_approach(rows, relation, road))
    result = {"case_id": contract["case_id"], "source_kind": relation["source_kind"],
              "source_complete": True, "selected": False, "accepted": False,
              "legal_verdict": None, "measurements": {}}
    for req in contract["requirements"]:
        if req["output_key"] not in ("curve_approach", "winding_approach") or req["method"] != "measure_curve_approach":
            raise ValueError("Measurement method differs from saved finalizer")
        result["measurements"][req["output_key"]] = {
            "method": req["method"], "value": value,
            "sources": {name: _sha(_required(folder, name)) for name in req["inputs"]}}
    return result


def _rows(folder: Path, name: str) -> list[dict]:
    return [json.loads(line) for line in _required(folder, name).read_text().splitlines()
            if line.strip()]


def _body_xy(vertices: list) -> set[tuple[float, float]]:
    return {(round(v[0], 5), round(v[1], 5)) for v in vertices}


def verify_original_joins(folder: Path, expected: int = 600) -> dict:
    names = ("native_samples.jsonl", "trace.jsonl", "capture/evidence.jsonl",
             "video_frames.jsonl", "body_history.jsonl", "capture/native/frames.jsonl")
    native, trace, evidence, mapping, body, frames = (_rows(folder, name) for name in names)
    if any(len(source) != expected for source in
           (native, trace, evidence, mapping, body, frames)):
        raise ValueError("Original Native/Core frame counts differ")
    last_frame, last_time = -1, -1.0
    for index, (n, t, e, m, b, f) in enumerate(zip(native, trace, evidence, mapping, body, frames)):
        frame, time_s = m.get("native_frame"), m.get("time_s")
        if (type(frame) is not int or frame <= last_frame or
                not isinstance(time_s, (int, float)) or time_s <= last_time or
                m.get("video_frame") != index or m.get("carla_frame") != frame):
            raise ValueError("Original frame/time map differs")
        last_frame, last_time = frame, time_s
        if any(row != frame for row in (n.get("native_frame"), t.get("frame"),
                                        e.get("original_frame"), b.get("frame"), f.get("frame"))):
            raise ValueError("Original Native/Core frame identity differs")
        if any(abs(float(row) - time_s) > 1e-4 for row in
               (n.get("time_s"), t.get("time_s"), e.get("recording_time_s"),
                b.get("time_s"))):
            raise ValueError("Original Native/Core timestamp differs")
        native_body = _body_xy(n.get("ego_body_vertices_m", []))
        captured_body = _body_xy(e.get("ego", {}).get("body_vertices_m", []))
        history_body = _body_xy(b.get("body_vertices_m", []))
        if len(native_body) != 4 or native_body != captured_body or native_body != history_body:
            raise ValueError("Original Native/Core full body differs")
    manifest = json.loads(_required(folder, "capture/manifest.json").read_text())
    if manifest.get("frames") != expected or manifest.get("extraction_confirmed") is not True:
        raise ValueError("Original Core extraction incomplete")
    return {"frames": expected, "first_native_frame": mapping[0]["native_frame"],
            "last_native_frame": mapping[-1]["native_frame"],
            "source_hashes": {name: _sha(folder / name) for name in names}}


def _video_frames(path: Path) -> int:
    _required(path.parent, path.name)
    result = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
        "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    if result.returncode or not result.stdout.strip().isdigit():
        raise ValueError("Original source video decode failed: " + path.name)
    return int(result.stdout.strip())


def finalize_attempt(folder: Path, output: Path) -> dict:
    """Join saved original sources and emit the pinned Native result schema."""
    from worker_exchange.native_output import validate_result

    folder, output = Path(folder).resolve(), Path(output).resolve()
    if output.exists() or (folder / "result.json").exists():
        raise ValueError("Retain prior analysis; choose a fresh attempt")
    config = json.loads(_required(folder, "config.json").read_text())
    contract = json.loads(_required(folder, config["measurement_contract"]).read_text())
    if contract["case_id"] != config["case_id"]:
        raise ValueError("Exact case and measurement contract differ")
    joined = verify_original_joins(folder)
    report = finalize(folder, contract, _sha(folder / "native_samples.jsonl"))
    measured = report["measurements"]["curve_approach"]["value"]
    videos = [name + ".mkv" for name in
              ("overview", "approach", "reference_corner", "driver_reference")]
    counts = {name: _video_frames(folder / name) for name in videos}
    if set(counts.values()) != {600}:
        raise ValueError("Original camera frame count differs")
    original = report["source_kind"] == "original_native_capture"
    target = {"probe_a": "measured_early_decrease_held",
              "curve_probe_b": "measured_no_material_decrease"}[config["case_suffix"]]
    original_rows = _rows(folder, "native_samples.jsonl")
    channel_dir = folder / "channels"
    if channel_dir.exists():
        raise ValueError("Derived channels already exist")
    channel_dir.mkdir()
    value_of = {
        "ego_pose": lambda row: row["ego_position_m"],
        "ego_speed": lambda row: math.sqrt(sum(v*v for v in row["ego_velocity_mps"])),
        "observed_speed": lambda row: math.sqrt(sum(v*v for v in row["ego_velocity_mps"])) / .44704,
        "other_vehicle_pose": lambda row: row["other_position_m"],
    }
    for channel in config["recording_description"]["channels"]:
        name = channel["name"]
        with (channel_dir / (name + ".jsonl")).open("x") as stream:
            for row in original_rows:
                stream.write(json.dumps({"time_s": row["time_s"], "value": value_of[name](row),
                                         "source_sha256": _sha(folder / "native_samples.jsonl")}) + "\n")
    evidence = []
    for channel in config["recording_description"]["channels"]:
        ref = "channels/" + channel["name"] + ".jsonl"
        _required(folder, ref)
        evidence.append({"name": channel["name"], "unit": channel["unit"],
                         "reference": ref})
    for item in config["recording_description"]["context_inputs"]:
        _required(folder, "context.json")
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": "context.json"})
    result = {"case_id": config["case_id"], "measured_values": measured,
        "target_checks": [{"target": "saved intersection approach-speed profile",
            "requested": target, "measured": measured["measured_relation"],
            "method": "source-hashed 600-frame Native velocity/pose windows",
            "tolerance": "3 mph reduction and 2 mph crossing hold are engineering surrogates",
            "matched": target == measured["measured_relation"],
            "physical_cause_confirmed": False,
            "cause_evidence": ["native_samples.jsonl", "trace.jsonl",
                               "video_frames.jsonl"]}],
        "setup_confirmed": False, "behavior_attempted": original,
        "maneuver_completed": original,
        "termination_reason": "600 saved source frames checked; necessity and legal review pending",
        "physical_failure_flags": ["reduction_necessity_unverified",
                                   "physical_hazard_causation_unverified"],
        "trace_reference": "trace.jsonl", "video_references": videos,
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["recording_description"],
        "recording_evidence": evidence,
        "realized_observables": {"approach_speed_delta_mph": {
            "value": measured["measured_decrease_mph"],
            "unit": "mph", "statistic": "approach minus pre-entry mean speed",
            "method": "three-axis Native velocity norm across saved windows",
            "time_window": "approach and pre-entry of 30 s attempt",
            "reference": "native_samples.jsonl"}},
        "provenance_kind": "native", "diagnostic_fixture": not original,
        "accepted": False, "legal_verdict_claimed": False}
    validate_result(result)
    report.update(format="c111294-saved-approach-analysis-v1", original_joins=joined,
                  video_frames=counts, diagnostic_fixture=not original,
                  analysis_complete=True,
                  limitations=["Necessity of speed reduction and physical causation await original review",
                               "No legal or recording acceptance verdict"])
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    (folder / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return report




if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", type=Path)
    parser.add_argument("--attempt", type=Path)
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--source-sha256")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.attempt:
        report = finalize_attempt(args.attempt, args.output)
    else:
        if not all((args.folder, args.contract, args.source_sha256)):
            parser.error("Saved measurement requires folder, contract and source SHA-256")
        contract = json.loads(args.contract.read_text())
        report = finalize(args.folder, contract, args.source_sha256)
        with args.output.open("x") as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write("\n")
    print(json.dumps({"case_id": report["case_id"], "passed": True,
                      "source_kind": report["source_kind"], "selected": False},
                     sort_keys=True))
