"""Measure other-first median-opening entry while ego approaches.

This preserves Native junction/highway identity, source frames and the Off
signal qualification. Entry order and speed are observations, not a legal yield
or statutory intersection determination.
"""

import hashlib
import json
import math
import argparse
import shutil
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon


REQUIRED = ("crossing_history.jsonl", "video_frames.jsonl", "junction_context.json")
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Missing finite Native observation")
    return float(value)


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _inside(actor, polygon):
    vertices = actor.get("body_vertices_xy_m")
    if not isinstance(vertices, list) or len(vertices) < 4:
        raise ValueError("Missing complete actor body")
    body = MultiPoint([(_number(v[0]), _number(v[1])) for v in vertices]).convex_hull
    return body.intersects(polygon)


def _body_center(actor):
    vertices = actor["body_vertices_xy_m"]
    return tuple(sum(_number(vertex[axis]) for vertex in vertices) / len(vertices)
                 for axis in (0, 1))


def analyze(root: Path, *, signal_mode: str = "off", allow_other_initially_inside: bool = False,
            opposing_left_exception: bool = False) -> dict:
    if signal_mode not in ("off", "operating"):
        raise ValueError("Unknown signal mode")
    root = Path(root)
    sources = {}
    for name in REQUIRED:
        path = root / name
        if not path.is_file():
            raise ValueError("Missing required source: " + name)
        sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    context = json.loads((root / "junction_context.json").read_text())
    for key in ("native_map_id", "intersection_id", "ego_highway_id", "other_highway_id",
                "ego_road_id", "other_road_id", "native_signal_id", "signal_governance_source",
                "signal_head_video_source", "intersection_polygon_source"):
        if context.get(key) is None:
            raise ValueError("Missing sourced crossing context: " + key)
    if context["ego_highway_id"] == context["other_highway_id"] and not opposing_left_exception:
        raise ValueError("Approaches must be from different highways")
    opposite_dot = None
    if opposing_left_exception:
        if not context.get("other_left_turn_intent_source"):
            raise ValueError("Missing sourced other left-turn intent")
        vectors = []
        for who in ("ego", "other"):
            vector = context.get(who + "_approach_direction_xy")
            if not isinstance(vector, list) or len(vector) != 2:
                raise ValueError("Missing sourced approach direction: " + who)
            vx, vy = (_number(value) for value in vector)
            length = math.hypot(vx, vy)
            if length <= 0:
                raise ValueError("Zero approach direction")
            vectors.append((vx / length, vy / length))
        opposite_dot = sum(a * b for a, b in zip(*vectors))
        # Geometry-quality test for opposed lane tangents, not a legal cutoff.
        if opposite_dot > -0.95:
            raise ValueError("Sourced approaches are not opposite")
    if context.get("installed_uncovered_vehicular_heads") is not True:
        raise ValueError("Uncovered vehicular signal heads not sourced")
    vertices = context.get("intersection_polygon_xy_m")
    if not isinstance(vertices, list) or len(vertices) < 3:
        raise ValueError("Missing sourced intersection polygon")
    polygon = Polygon([(_number(v[0]), _number(v[1])) for v in vertices])
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("Invalid intersection polygon")
    rows, frames = _rows(root / "crossing_history.jsonl"), _rows(root / "video_frames.jsonl")
    if len(rows) < 3 or len(rows) != len(frames):
        raise ValueError("Incomplete crossing/frame history")
    prior = (-1, -math.inf)
    first_entry = {"ego": None, "other": None}
    prior_inside = {"ego": False, "other": False}
    occupancy = {"ego": [], "other": []}
    observed_signal_states = []
    left_turn_headings = []
    approach_centers = {"ego": [], "other": []}
    other_initially_inside = False
    samples = []
    for index, (row, frame) in enumerate(zip(rows, frames)):
        fid, time = row.get("frame"), _number(row.get("time_s"))
        if type(fid) is not int or fid <= prior[0] or time <= prior[1]:
            raise ValueError("Nonmonotone original frame/time")
        prior = (fid, time)
        if frame.get("video_frame") != index or frame.get("carla_frame") != fid or frame.get("time_s") != time:
            raise ValueError("Original video frame join failed")
        if row.get("native_signal_id") != context["native_signal_id"]:
            raise ValueError("Identified signal source changed")
        state = row.get("signal_state")
        if signal_mode == "off" and state != "Off":
            raise ValueError("Identified signal not observed Off")
        if signal_mode == "operating" and state not in ("Red", "Yellow", "Green"):
            raise ValueError("Identified signal not observed operating")
        observed_signal_states.append(state)
        sample = {"frame": fid, "time_s": time}
        for who in ("ego", "other"):
            actor = row.get(who)
            if not isinstance(actor, dict) or actor.get("intersection_id") != context["intersection_id"] or actor.get("road_id") != context[who + "_road_id"]:
                raise ValueError("Actor not on sourced junction approach")
            if opposing_left_exception and who == "other":
                if actor.get("turn_intent") != "left":
                    raise ValueError("Original other left-turn intent missing")
                left_turn_headings.append({"frame": fid, "time_s": time,
                                           "heading_deg": _number(actor.get("heading_deg"))})
            inside = _inside(actor, polygon)
            if opposing_left_exception:
                approach_centers[who].append(_body_center(actor))
            if index == 0 and inside:
                if who != "other" or not allow_other_initially_inside:
                    raise ValueError("No observed pre-entry approach")
                other_initially_inside = True
            distance = _number(actor.get("distance_to_intersection_m"))
            speed = _number(actor.get("speed_mps"))
            if distance < 0 or speed < 0:
                raise ValueError("Invalid approach distance or speed")
            if inside and not prior_inside[who] and first_entry[who] is None and not (index == 0 and who == "other"):
                first_entry[who] = {"frame": fid, "time_s": time}
            if inside and not prior_inside[who]:
                occupancy[who].append({"entry_frame": None if index == 0 else fid,
                                       "entry_time_s": None if index == 0 else time,
                                       "exit_frame": None, "exit_time_s": None})
            if not inside and prior_inside[who]:
                occupancy[who][-1]["exit_frame"] = fid
                occupancy[who][-1]["exit_time_s"] = time
            prior_inside[who] = inside
            sample[who] = {"body_in_intersection": inside, "distance_to_intersection_m": distance,
                           "speed_mps": speed}
        samples.append(sample)
    if (first_entry["other"] is None and not other_initially_inside) or first_entry["ego"] is None:
        raise ValueError("Required body entry not observed")
    observed_forward_progress = None
    if opposing_left_exception:
        observed_forward_progress = {}
        for who, direction in zip(("ego", "other"), vectors):
            start, end = approach_centers[who][0], approach_centers[who][-1]
            displacement = tuple(end[axis] - start[axis] for axis in (0, 1))
            projection = sum(displacement[axis] * direction[axis] for axis in (0, 1))
            if projection <= 0:
                raise ValueError("Original body motion contradicts sourced approach direction: " + who)
            observed_forward_progress[who] = {"body_displacement_xy_m": displacement,
                                              "projection_on_approach_direction_m": projection}
    other_frame = first_entry["other"]["frame"] if first_entry["other"] else None
    other_index = next((i for i, sample in enumerate(samples) if sample["frame"] == other_frame), None)
    ego_approaching_at_other_entry = (other_index is not None and not samples[other_index]["ego"]["body_in_intersection"]
        and samples[other_index]["ego"]["distance_to_intersection_m"] > 0
        and other_index + 1 < len(samples)
        and samples[other_index + 1]["ego"]["distance_to_intersection_m"] < samples[other_index]["ego"]["distance_to_intersection_m"])
    ego_speeds_while_other_inside = [sample["ego"]["speed_mps"] for sample in samples
                                     if sample["other"]["body_in_intersection"] and not sample["ego"]["body_in_intersection"]]
    other_inside_while_ego_outside = [sample for sample in samples
                                      if sample["other"]["body_in_intersection"] and
                                      not sample["ego"]["body_in_intersection"]]
    return {"format": "worker-median-opening-crossing-observations", "sources": sources,
            "intersection_id": context["intersection_id"],
            "highway_ids": [context["ego_highway_id"], context["other_highway_id"]],
            "signal_mode": signal_mode,
            "observed_signal_states": observed_signal_states,
            "first_body_entry": first_entry,
            "other_initially_inside_observed": other_initially_inside,
            "occupancy_intervals": occupancy,
            "other_entered_before_ego_observed": (first_entry["other"]["time_s"] < first_entry["ego"]["time_s"]
                                                if first_entry["other"] else None),
            "ego_approaching_at_other_entry_observed": ego_approaching_at_other_entry,
            "minimum_ego_speed_while_other_inside_mps": min(ego_speeds_while_other_inside) if ego_speeds_while_other_inside else None,
            "ego_speed_samples_while_other_inside": [{"frame": sample["frame"],
                                                       "time_s": sample["time_s"],
                                                       "speed_mps": sample["ego"]["speed_mps"]}
                                                      for sample in other_inside_while_ego_outside],
            "ego_entered_while_other_inside_observed": any(sample["ego"]["body_in_intersection"] and
                                                          sample["other"]["body_in_intersection"]
                                                          for sample in samples),
            "other_exit_observed": occupancy["other"][-1]["exit_frame"] is not None,
            "opposing_left_exception_observations": ({
                "approach_direction_dot": opposite_dot,
                "geometry_quality_tolerance_not_legal": 0.95,
                "left_turn_intent_source": context["other_left_turn_intent_source"],
                "left_turn_intent_in_original_rows": True,
                "original_body_motion": observed_forward_progress,
                "other_heading_samples_deg": left_turn_headings,
                "statutory_exception_judgment": "unresolved"}
                if opposing_left_exception else None),
            "samples": samples,
            "statutory_roadway_crossing_judgment": "unresolved",
            "statutory_inoperative_signal_judgment": "unresolved",
            "right_of_way_judgment": "unresolved"}


def measure_crossing_context(report, context):
    return {"intersection_id": report["intersection_id"],
            "highway_ids": report["highway_ids"],
            "native_map_id": context["native_map_id"],
            "intersection_polygon_source": context["intersection_polygon_source"]}


def measure_entry_order(report, context):
    return {"first_body_entry": report["first_body_entry"],
            "other_before_ego": report["other_entered_before_ego_observed"],
            "ego_approaching_at_other_entry": report["ego_approaching_at_other_entry_observed"]}


def measure_occupancy(report, context):
    return {"occupancy_intervals": report["occupancy_intervals"],
            "ego_speed_samples_while_other_inside": report["ego_speed_samples_while_other_inside"]}


def measure_signal_context(report, context):
    return {"native_signal_id": context["native_signal_id"],
            "signal_governance_source": context["signal_governance_source"],
            "observed_signal_states": report["observed_signal_states"],
            "official_device_judgment": "unresolved"}


def measure_opposite_turn_context(report, context):
    return {"opposite_left_turn_observations": report["opposing_left_exception_observations"],
            "exception_judgment": "unresolved"}


def _contract_measurements(attempt, report):
    context = json.loads((attempt / "junction_context.json").read_text())
    definitions = {
        "crossing_identity": (measure_crossing_context, ("junction_context.json",)),
        "entry_order": (measure_entry_order, REQUIRED),
        "other_occupancy": (measure_occupancy, REQUIRED),
        "device_context": (measure_signal_context, ("junction_context.json", "crossing_history.jsonl")),
        "opposite_turn_context": (measure_opposite_turn_context, ("junction_context.json",)),
    }
    measurements = {}
    for key, (method, inputs) in definitions.items():
        measurements[key] = {"method": method.__name__, "value": method(report, context),
                             "sources": {name: hashlib.sha256((attempt / name).read_bytes()).hexdigest()
                                         for name in inputs}}
    return measurements


def finalize_saved(attempt: Path, output: Path) -> dict:
    """Derive evidence channels only from retained original rows and context."""
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / "result.json").exists() or (attempt / "channels").exists():
        raise ValueError("Fresh saved-processing version required")
    from worker_exchange.native_output import physical_result, write_result
    required = ("config.json", "trace.jsonl", "capture/evidence.jsonl", *REQUIRED,
                *(camera + ".mkv" for camera in CAMERAS))
    for name in required:
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    case_id = config.get("selected_case_id", "")
    prefix = "testing__C125697__NRS-484B-250-1__motor_vehicle_driver__"
    if (config.get("cell_id") != "C125697" or config.get("law_id") != "NRS-484B-250-1" or
            not case_id.startswith(prefix) or not config.get("recording_description", {}).get("channels")):
        raise ValueError("Wrong exact C125697 capture identity or description")
    suffix = case_id.removeprefix(prefix)
    if suffix not in ("off_other_enters_first", "off_ego_enters_first", "off_other_already_inside",
                      "operative_signal_exclusion", "opposite_left_exception"):
        raise ValueError("Unknown selected C125697 branch")
    report = analyze(attempt,
                     signal_mode="operating" if suffix == "operative_signal_exclusion" else "off",
                     allow_other_initially_inside=suffix == "off_other_already_inside",
                     opposing_left_exception=suffix == "opposite_left_exception")
    rows, frames, trace = (_rows(attempt / name) for name in
                           ("crossing_history.jsonl", "video_frames.jsonl", "trace.jsonl"))
    if len(rows) != len(frames) or len(trace) != len(frames) or any(
            original.get("frame") != frame.get("carla_frame") or
            original.get("time_s") != frame.get("time_s")
            for original, frame in zip(trace, frames)):
        raise ValueError("Original trace/video frame join failed")
    values = {
        "ego_speed": ("m/s", lambda row, sample: sample["ego"]["speed_mps"]),
        "other_speed": ("m/s", lambda row, sample: sample["other"]["speed_mps"]),
        "ego_approach_distance": ("m", lambda row, sample: sample["ego"]["distance_to_intersection_m"]),
        "other_approach_distance": ("m", lambda row, sample: sample["other"]["distance_to_intersection_m"]),
        "ego_body_inside": ("boolean", lambda row, sample: sample["ego"]["body_in_intersection"]),
        "other_body_inside": ("boolean", lambda row, sample: sample["other"]["body_in_intersection"]),
        "signal_state": ("device state", lambda row, sample: row["signal_state"]),
        "ego_position": ("m", lambda row, sample: _body_center(row["ego"])),
        "other_position": ("m", lambda row, sample: _body_center(row["other"])),
    }
    derived = {name: [fn(row, sample) for row, sample in zip(rows, report["samples"])]
               for name, (_, fn) in values.items()}
    evidence_root = attempt / "evidence"
    evidence_root.mkdir(exist_ok=True)
    for name in ("config.json", "trace.jsonl", *REQUIRED):
        shutil.copyfile(attempt / name, evidence_root / name)
    shutil.copytree(attempt / "capture", evidence_root / "capture", dirs_exist_ok=True)
    channels = attempt / "channels"
    channels.mkdir()
    evidence = []
    for name, (unit, _) in values.items():
        reference = "channels/" + name + ".jsonl"
        with (attempt / reference).open("x") as stream:
            for row, value in zip(rows, derived[name]):
                stream.write(json.dumps({"time_s": row["time_s"], "original_frame": row["frame"],
                                         "value": value}, allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": unit, "reference": reference})
    evidence.append({"name": "intersection_id", "unit": "structured record",
                     "reference": "junction_context.json"})
    checksums = {"evidence/" + path.relative_to(evidence_root).as_posix():
                 hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in evidence_root.rglob("*") if path.is_file()}
    (attempt / "evidence-checksums.json").write_text(json.dumps(checksums, sort_keys=True) + "\n")
    result = {
        "case_id": case_id,
        "measured_values": {"first_body_entry": report["first_body_entry"],
                            "occupancy_intervals": report["occupancy_intervals"],
                            "observed_signal_states": report["observed_signal_states"],
                            "ego_approaching_at_other_entry_observed":
                                report["ego_approaching_at_other_entry_observed"]},
        "target_checks": [{"target": "other_enters_before_ego", "requested": suffix == "off_other_enters_first",
                           "measured": report["other_entered_before_ego_observed"],
                           "method": "source-hashed complete-body entry and original frame join",
                           "tolerance": 0,
                           "matched": report["other_entered_before_ego_observed"] is True,
                           "physical_cause_confirmed": False,
                           "cause_evidence": list(report["sources"])}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False, "termination_reason": "Saved source assessment pending",
        "physical_failure_flags": ["Native geometry, signal visibility and legal judgments require original review"],
        "trace_reference": "trace.jsonl", "video_references": [name + ".mkv" for name in CAMERAS],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["recording_description"],
        "recording_evidence": evidence, "source_evidence_hashes": report["sources"],
        "capture_evidence_sha256": hashlib.sha256((attempt / "capture/evidence.jsonl").read_bytes()).hexdigest(),
        "realized_observables": {},
    }
    result = physical_result(attempt, result)
    write_result(attempt, result)
    analysis = {"format": "worker-analysis-report", "case_id": case_id,
                "source_report": report, "source_hashes": report["sources"],
                "measurements": _contract_measurements(attempt, report),
                "physical_checks": result["physical_checks"],
                "realized_observables": result["realized_observables"],
                "provenance_kind": result["provenance_kind"],
                "diagnostic_fixture": result["diagnostic_fixture"],
                "legal_verdict_asserted": False, "analysis_complete": True}
    output.write_text(json.dumps(analysis, indent=2, allow_nan=False) + "\n")
    return analysis


def main():
    parser = argparse.ArgumentParser(description="Finalize saved median-opening crossing observations")
    parser.add_argument("source_dir", type=Path, nargs="?")
    parser.add_argument("output_json", type=Path, nargs="?")
    parser.add_argument("--signal-mode", choices=("off", "operating"), default="off")
    parser.add_argument("--allow-other-initially-inside", action="store_true")
    parser.add_argument("--opposing-left-exception", action="store_true")
    parser.add_argument("--attempt", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.attempt:
        if not args.output:
            parser.error("--output required with --attempt")
        finalize_saved(args.attempt, args.output)
        return
    if not args.source_dir or not args.output_json:
        parser.error("source_dir and output_json required for measurement mode")
    result = analyze(args.source_dir, signal_mode=args.signal_mode,
                     allow_other_initially_inside=args.allow_other_initially_inside,
                     opposing_left_exception=args.opposing_left_exception)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
