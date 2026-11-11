"""Saved-only original-source C129731 motion and sight-line measurements."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from runner import CASES
from site_construction import validate_site
from visibility_measure import summarize_native_frame

CAMERAS = ("overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")
REQUIRED = ("config.json", "motion_history.jsonl", "video_frames.jsonl",
            "trace.jsonl", "capture/evidence.jsonl", "turn_history.jsonl",
            "curve_context.json", *CAMERAS)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _velocity(actor):
    velocity = actor["velocity_xyz_mps"]
    if not isinstance(velocity, list) or len(velocity) != 3 or any(
            type(v) not in (int, float) or not math.isfinite(v) for v in velocity):
        raise ValueError("Finite original actor velocity required")
    return math.sqrt(sum(v*v for v in velocity))


def analyze_sources(attempt):
    attempt = Path(attempt)
    for name in REQUIRED[:7]:
        if not (attempt/name).is_file():
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt/"config.json").read_text())
    case = config.get("selected_case_id")
    if case not in CASES or config.get("law_id") != "NRS-484B-407" or config.get("cell_id") != "C129731":
        raise ValueError("Exact C129731 saved case required")
    site_path = attempt/config["site_source"]["path"]
    if not site_path.is_file() or _sha(site_path) != config["site_source"]["sha256"]:
        raise ValueError("Saved site source changed")
    site = validate_site(json.loads(site_path.read_text()))
    if (site["feature"], site["probe"]) != CASES[case]:
        raise ValueError("Saved site differs from exact case")
    mapping, motion = _rows(attempt/"video_frames.jsonl"), _rows(attempt/"motion_history.jsonl")
    trace, evidence = _rows(attempt/"trace.jsonl"), _rows(attempt/"capture/evidence.jsonl")
    turns = _rows(attempt/"turn_history.jsonl")
    context = json.loads((attempt/"curve_context.json").read_text())
    if (context.get("site_source_sha256") != config["site_source"]["sha256"] or
            context.get("feature") != site["feature"] or
            context.get("incoming_lanes") != site["incoming_lanes"] or
            context.get("turn_site_xyz_m") != site["turn_site_xyz_m"]):
        raise ValueError("Original curve/crest context differs from sourced site")
    count = config["rate_hz"]*config["duration_s"]
    if not all(len(rows) == count for rows in (mapping, motion, trace, evidence, turns)):
        raise ValueError("Original motion, rays, trace and four-view frame count differ")
    lane_ids = [site["incoming_lanes"][name]["lane_id"]
                for name in ("approach_a", "approach_b")]
    sight, turn_distances = [], []
    source_sha = _sha(attempt/"capture/evidence.jsonl")
    previous_time = None
    for index, (frame, row, tick, native, turn) in enumerate(zip(mapping, motion, trace, evidence, turns)):
        identity = frame.get("native_frame")
        time = frame.get("time_s")
        if (frame.get("video_frame") != index or type(identity) is not int or
                type(time) not in (int, float) or not math.isfinite(time) or
                (previous_time is not None and time <= previous_time) or
                row.get("video_frame") != index or row.get("native_frame") != identity or
                tick.get("frame") != identity or tick.get("time_s") != time or
                native.get("original_frame") != identity or native.get("recording_time_s") != time or
                turn.get("frame") != identity or turn.get("time_s") != time):
            raise ValueError("Original frame/time join differs")
        previous_time = time
        if row.get("site_source_sha256") != config["site_source"]["sha256"]:
            raise ValueError("Original motion site binding differs")
        if set(row.get("approaches", {})) != set(site["incoming_lanes"]):
            raise ValueError("Both recorded approaching vehicles required")
        for name, vehicle in row["approaches"].items():
            lane = site["incoming_lanes"][name]
            if vehicle.get("road_lane") != [lane["road_id"], lane["lane_id"]]:
                raise ValueError("Recorded approaching road/lane differs: " + name)
            _velocity(vehicle)
        ego = row.get("ego", {})
        _velocity(ego)
        position = ego.get("location_xyz_m")
        if not isinstance(position, list) or len(position) != 3:
            raise ValueError("Original ego position required")
        turn_distances.append(math.dist(position[:2], site["turn_site_xyz_m"][:2]))
        visibility = native.get("visibility")
        if not isinstance(visibility, dict):
            raise ValueError("Missing original sight rays at frame " + str(identity))
        sight.append(summarize_native_frame(visibility, source_sha, lane_ids))
    turn_index = min(range(count), key=turn_distances.__getitem__)
    first, last = motion[0]["ego"], motion[-1]["ego"]
    heading_difference = abs((last["yaw_deg"]-first["yaw_deg"]+180) % 360-180)
    at_turn = sight[turn_index]
    return {"case_id": case, "site": site, "config": config,
            "turn_frame": mapping[turn_index]["native_frame"],
            "turn_frame_distance_m": turn_distances[turn_index],
            "turn_frame_sight": at_turn,
            "observed_heading_change_deg": heading_difference,
            "observed_exit_distance_m": math.dist(last["location_xyz_m"][:2],
                                                    site["u_turn_route_xyz_m"][-1][:2]),
            "observed_final_speed_mps": _velocity(last),
            "all_frame_sight": sight,
            "motion_rows": motion, "frame_rows": mapping,
            "source_hashes": {**{name: _sha(attempt/name) for name in REQUIRED[:7]},
                              config["site_source"]["path"]: _sha(site_path)}}


def measure_visibility(report):
    return {"at_turn": report["turn_frame_sight"],
            "turn_frame": report["turn_frame"],
            "statutory_reference_m": 152.4,
            "actual_driver_visibility_verified": False}


def measure_turn(report):
    return {"observed_heading_change_deg": report["observed_heading_change_deg"],
            "turn_frame_distance_m": report["turn_frame_distance_m"],
            "feature": report["site"]["feature"],
            "source_status": report["site"]["source_status"],
            "legal_maneuver_judgment": None}


def finalize(attempt, output):
    from worker_exchange.native_output import physical_result, write_result

    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt/"result.json").exists() or (attempt/"channels").exists():
        raise ValueError("Retain original saved finalization; choose a fresh attempt")
    for name in REQUIRED:
        if not (attempt/name).is_file():
            raise ValueError("Missing required source: " + name)
    report = analyze_sources(attempt)
    config, site = report["config"], report["site"]
    channels = attempt/"channels"
    channels.mkdir()
    for name, rows in (
            ("sight_distance", ({"time_s": f["time_s"], "value": v} for f, v in
                                zip(report["frame_rows"], report["all_frame_sight"]))),
            ("u_turn_motion", ({"time_s": f["time_s"], "value": m["ego"]} for f, m in
                               zip(report["frame_rows"], report["motion_rows"]))),
            ("approaching_actors", ({"time_s": f["time_s"], "value": m["approaches"]} for f, m in
                                    zip(report["frame_rows"], report["motion_rows"])))):
        (channels/(name+".jsonl")).write_text("".join(json.dumps(row, allow_nan=False)+"\n" for row in rows))
    completed = (report["observed_heading_change_deg"] >= 150 and
                 report["observed_exit_distance_m"] <= 2 and
                 report["observed_final_speed_mps"] <= .5)
    proxy = report["turn_frame_sight"]["pinned_proxy_m"]
    probe = site["probe"]
    matched = (proxy is not None and
               ((probe == "short_of_500ft" and proxy < 152.4) or
                (probe == "at_500ft" and abs(proxy-152.4) <= .25) or
                (probe == "beyond_500ft" and proxy > 152.4)))
    result = {"case_id": report["case_id"],
              "measured_values": {"turn_frame": report["turn_frame"],
                                  "turn_frame_sight_proxy_m": proxy,
                                  "observed_heading_change_deg": report["observed_heading_change_deg"]},
              "target_checks": [{"target": "two_direction_virtual_eye_sight_probe",
                                 "requested": probe, "measured": proxy,
                                 "method": "original pinned nine-body ray proxy at nearest recorded turn-site frame",
                                 "tolerance": "0.25 m engineering bracket for at_500ft; no legal interpretation",
                                 "matched": bool(matched), "physical_cause_confirmed": False,
                                 "cause_evidence": ["capture/evidence.jsonl", "motion_history.jsonl"]}],
              "setup_confirmed": False, "behavior_attempted": True,
              "maneuver_completed": bool(completed),
              "termination_reason": "Saved original-source motion and ray analysis; physical review pending",
              "physical_failure_flags": ["actual driver visibility and realized curve/crest occlusion unverified"],
              "trace_reference": "trace.jsonl", "video_references": list(CAMERAS),
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": config.get("recording_description", {}),
              "recording_evidence": [{"name": name, "unit": "structured record",
                                      "reference": "channels/"+name+".jsonl"}
                                     for name in ("sight_distance", "u_turn_motion", "approaching_actors")],
              "source_evidence_hashes": {**report["source_hashes"],
                                         **{name: _sha(attempt/name) for name in CAMERAS}},
              "capture_evidence_sha256": report["source_hashes"]["capture/evidence.jsonl"],
              "realized_observables": {}}
    result = physical_result(attempt, result)
    write_result(attempt, result)
    measurements = {
        "visibility_at_turn": {"method": "measure_visibility", "value": measure_visibility(report),
                               "sources": {name: report["source_hashes"][name] for name in
                                           ("capture/evidence.jsonl", "motion_history.jsonl", "video_frames.jsonl")}},
        "turn_and_site": {"method": "measure_turn", "value": measure_turn(report),
                          "sources": {name: report["source_hashes"][name] for name in
                                      ("turn_history.jsonl", "curve_context.json", "motion_history.jsonl",
                                       "video_frames.jsonl")}}}
    output.write_text(json.dumps({"format": "worker-analysis-report",
                                  "case_id": report["case_id"], "turn_frame": report["turn_frame"],
                                  "turn_frame_sight": report["turn_frame_sight"],
                                  "observed_heading_change_deg": report["observed_heading_change_deg"],
                                  "measurements": measurements,
                                  "physical_checks": result["physical_checks"],
                                  "realized_observables": result["realized_observables"],
                                  "provenance_kind": result["provenance_kind"],
                                  "diagnostic_fixture": result["diagnostic_fixture"],
                                  "limitations": ["Synthetic diagnostic cannot prove physical visibility or legal outcome"],
                                  "analysis_complete": True,
                                  "physical_acceptance_claimed": False,
                                  "legal_acceptance_claimed": False}, indent=2, allow_nan=False)+"\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
