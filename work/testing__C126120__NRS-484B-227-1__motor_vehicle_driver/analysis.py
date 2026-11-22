"""Saved-only C126120 body/median measurements; no legal evaluator."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from uturn_audit import measure
from divider_construction import verify_recorded_divider


SOURCES = ("median-context.json", "divider-geometry.json", "ego-body-history.jsonl", "controller-history.jsonl",
           "video_frames.jsonl", "trace.jsonl", "road.xodr",
           "reviewed-median-context.json", "authority-review-source.json")
MEASUREMENT_SOURCES = ("median-context.json", "divider-geometry.json", "ego-body-history.jsonl",
                       "controller-history.jsonl", "video_frames.jsonl", "trace.jsonl")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(attempt, acquisition, name):
    path = attempt/name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    provenance = json.loads((attempt/"acquisition-provenance.json").read_text())
    if provenance.get("provenance_kind") == "native" and provenance.get("diagnostic_fixture") is False:
        expected_kind = "original_native"
    elif provenance.get("provenance_kind") == "synthetic_fixture" and provenance.get("diagnostic_fixture") is True:
        expected_kind = "diagnostic_fixture"
    else:
        raise ValueError("Unknown or contradictory acquisition provenance")
    item = acquisition.get(name, {})
    if item.get("kind") != expected_kind or item.get("sha256") != sha(path):
        raise ValueError("Missing or stale provenance-bound source: " + name)
    return path


def rows(path):
    values = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not values:
        raise ValueError("Empty original Native history: " + path.name)
    return values


def measure_median_uturn(context, body):
    """Measured original geometry only; administrative facts remain unresolved."""
    return measure({"context":context,"samples":body})


def build_report(attempt):
    attempt = Path(attempt)
    acquisition = json.loads((attempt/"acquisition.json").read_text())
    paths = {name:source(attempt, acquisition, name) for name in SOURCES}
    provenance = json.loads((attempt/"acquisition-provenance.json").read_text())
    if not ((provenance.get("provenance_kind") == "native" and
             provenance.get("diagnostic_fixture") is False) or
            (provenance.get("provenance_kind") == "synthetic_fixture" and
             provenance.get("diagnostic_fixture") is True)):
        raise ValueError("explicit Native or diagnostic provenance required")
    context = json.loads(paths["median-context.json"].read_text())
    reviewed = json.loads(paths["reviewed-median-context.json"].read_text())
    reviewed_hash = sha(paths["reviewed-median-context.json"])
    if (context.get("reviewed_context_sha256") != reviewed_hash or
            provenance.get("reviewed_context_sha256") != reviewed_hash):
        raise ValueError("reviewed median context identity differs")
    if any(context.get(key) != value for key,value in reviewed["context"].items()):
        raise ValueError("saved median context differs from retained source")
    if sha(paths["road.xodr"]) != context["map_source_sha256"]:
        raise ValueError("saved OpenDRIVE differs from reviewed map")
    if sha(paths["authority-review-source.json"]) != context["authority_review_source_sha256"]:
        raise ValueError("saved authority review source differs")
    divider = verify_recorded_divider(context,reviewed["divider_props"],
                                     json.loads(paths["divider-geometry.json"].read_text()))
    body = rows(paths["ego-body-history.jsonl"])
    controls = rows(paths["controller-history.jsonl"])
    mapping = rows(paths["video_frames.jsonl"])
    trace_rows = rows(paths["trace.jsonl"])
    if not (len(body) == len(controls) == len(mapping) == len(trace_rows)):
        raise ValueError("original body, control, frame-map and trace lengths differ")
    for index, (sample, control, frame, trace_row) in enumerate(zip(body,controls,mapping,trace_rows)):
        identity = (sample.get("frame"), sample.get("time_s"))
        if (identity != (control.get("frame"),control.get("time_s")) or
                identity != (frame.get("carla_frame"),frame.get("time_s")) or
                sample.get("frame") != trace_row.get("frame") or
                frame.get("video_frame") != index or
                sample.get("actor_id") != context.get("ego_actor_id") or
                control.get("ego_actor_id") != context.get("ego_actor_id")):
            raise ValueError("original actor/frame/time identity join differs")
    observed = measure_median_uturn(context,body)
    observed.update(ego_actor_id=context["ego_actor_id"],
                    divider_geometry=divider,
                    first_time_s=body[0]["time_s"],last_time_s=body[-1]["time_s"])
    return {"format":"worker-analysis-report",
            "measurements":{"median_uturn_measurement":{
                "value":observed,
                "method":"measure_median_uturn",
                "sources":{name:acquisition[name]["sha256"] for name in MEASUREMENT_SOURCES}}},
            "limitations":["Public-authority establishment requires independent source review.",
                           "Physical opening contact does not establish a legal exception."],
            "analysis_complete":True,"legal_verdict_claimed":False}


def saved_result(attempt, report):
    from worker_exchange.native_output import physical_result, validate_result
    attempt = Path(attempt)
    config = json.loads((attempt/"config.json").read_text())
    construction = json.loads((attempt/"construction.json").read_text())
    acquisition = json.loads((attempt/"acquisition.json").read_text())
    if (config.get("law_id"),config.get("cell_id"),config.get("actor")) != (
            "NRS-484B-227-1","C126120","motor_vehicle_driver"):
        raise ValueError("saved finalizer assignment identity differs")
    context = json.loads(source(attempt,acquisition,"median-context.json").read_text())
    description = construction["recording_description"]
    expected = config["case"]["recording_description"]
    if description != expected:
        raise ValueError("recording description differs from exact config")
    closed_approach = config["case"].get("physical_target") == "closed_divider_approach"
    wrong_roadway = config["case"].get("physical_target") == "non_right_roadway"
    no_turn = config["case"].get("physical_target") == "source_right_roadway_continuation"
    criterion = "travel_progress" if closed_approach or wrong_roadway or no_turn else "turn"
    if (config["physical_completion"]["motion_source"] != "ego-body-history.jsonl" or
            config["physical_completion"]["criterion"] != criterion):
        raise ValueError("physical completion differs from original U-turn history")
    body = rows(source(attempt,acquisition,"ego-body-history.jsonl"))
    values = {
        "ego_body_history":[(r["time_s"],r["body_vertices_xy_m"]) for r in body],
        "ego_heading_history":[(r["time_s"],r["heading_deg"]) for r in body],
        "ego_velocity_history":[(r["time_s"],r["velocity_xy_mps"]) for r in body]}
    contexts = {"median_geometry":{key:value for key,value in context.items()
                                      if key != "ego_actor_id"},
                "authority_review":json.loads(source(attempt,acquisition,
                                                       "authority-review-source.json").read_text())}
    output = attempt/"channels"
    output.mkdir(exist_ok=True)
    evidence = []
    for item in description["channels"]:
        name = item["name"]
        if name not in values:
            raise ValueError("Unsupported declared channel: "+name)
        path = output/(name+".jsonl")
        with path.open("x") as stream:
            for time_s,value in values[name]:
                stream.write(json.dumps({"time_s":time_s,"value":value},allow_nan=False)+"\n")
        evidence.append({"name":name,"unit":item["unit"],
                         "reference":str(path.relative_to(attempt))})
    context_path = output/"context.json"
    context_path.write_text(json.dumps(contexts,allow_nan=False)+"\n")
    for item in description["context_inputs"]:
        if item["name"] not in contexts:
            raise ValueError("Unsupported declared context: "+item["name"])
        evidence.append({"name":item["name"],"unit":item["unit"],
                         "reference":str(context_path.relative_to(attempt))})
    observed = report["measurements"]["median_uturn_measurement"]["value"]
    requested = config["case"]["multiple_movement_requested"]
    if no_turn:
        stayed = (observed["source_right_roadway_all_frames"] and
                  observed["source_right_roadway_final_occupancy"] and
                  not observed["opening_contact_frames"] and
                  not observed["closed_divider_contact_frames"] and
                  not observed["u_turn_orientation_observed"] and
                  not observed["destination_right_roadway_departure_observed"])
        target_checks = [{"target":"source right roadway continued without turn",
            "requested":True,"measured":stayed,
            "method":"original full-body roadway occupancy and heading history",
            "tolerance":0,"matched":stayed,
            "physical_cause_confirmed":False,
            "cause_evidence":report["measurements"]["median_uturn_measurement"]["sources"]}]
    elif wrong_roadway:
        reached_wrong = (observed["non_right_roadway_final_occupancy"] and
                         bool(observed["opening_full_body_frames"]) and
                         any(item["through_opening"] for item in
                             observed["roadway_centerline_crossings"]) and
                         not observed["closed_divider_contact_frames"] and
                         not observed["destination_right_roadway_departure_observed"])
        target_checks = [{"target":"non-right roadway reached through opening",
            "requested":True,"measured":reached_wrong,
            "method":"original final body occupancy and original centerline crossing",
            "tolerance":0,"matched":reached_wrong,
            "physical_cause_confirmed":False,
            "cause_evidence":report["measurements"]["median_uturn_measurement"]["sources"]},
            {"target":"destination right roadway not reached",
             "requested":False,
             "measured":observed["destination_right_roadway_departure_observed"],
             "method":"original final body versus reviewed destination right roadway",
             "tolerance":0,
             "matched":not observed["destination_right_roadway_departure_observed"],
             "physical_cause_confirmed":False,
             "cause_evidence":report["measurements"]["median_uturn_measurement"]["sources"]}]
    elif closed_approach:
        clearance = observed["final_closed_divider_clearance_m"]
        approach = (not observed["opening_contact_frames"] and
                    not observed["closed_divider_contact_frames"] and
                    .0 < clearance <= 1.0)
        target_checks = [{"target":"closed-divider approach with full-body clearance",
            "requested":True,"measured":approach,
            "method":"original body distance to the reviewed closed divider at final frame",
            "tolerance":"0 < clearance <= 1 metre engineering approach window",
            "matched":approach,"physical_cause_confirmed":False,
            "cause_evidence":report["measurements"]["median_uturn_measurement"]["sources"]},
            {"target":"destination right roadway not reached",
             "requested":False,
             "measured":observed["destination_right_roadway_departure_observed"],
             "method":"original final body versus reviewed destination right roadway",
             "tolerance":0,
             "matched":not observed["destination_right_roadway_departure_observed"],
             "physical_cause_confirmed":False,
             "cause_evidence":report["measurements"]["median_uturn_measurement"]["sources"]}]
    else:
        target_checks = [{"target":"realized multiple-movement U-turn",
            "requested":requested,"measured":observed["multiple_movement_observed"],
            "method":"original signed velocity and body displacement before/after reverse interval",
            "tolerance":0,"matched":observed["multiple_movement_observed"] == requested,
            "physical_cause_confirmed":False,
            "cause_evidence":report["measurements"]["median_uturn_measurement"]["sources"]},
           {"target":"full-body opening crossing without closed-divider contact",
            "requested":True,"measured":observed["engineering_crossing_observed"],
            "method":"original body intersection with reviewed opening and closed-divider geometry",
            "tolerance":0,"matched":observed["engineering_crossing_observed"],
            "physical_cause_confirmed":False,
            "cause_evidence":report["measurements"]["median_uturn_measurement"]["sources"]}]
    result = {"case_id":config["selected_case_id"],"measured_values":observed,
        "target_checks":target_checks,
        "setup_confirmed":False,"behavior_attempted":False,"maneuver_completed":False,
        "termination_reason":"Saved original evidence assessment pending",
        "physical_failure_flags":[],"trace_reference":"trace.jsonl",
        "video_references":["overview.mkv","approach.mkv","reference_corner.mkv",
                            "driver_reference.mkv"],
        "video_frame_map_reference":"video_frames.jsonl",
        "recording_description":description,"recording_evidence":evidence,
        "realized_observables":{}}
    result = physical_result(attempt,result)
    validate_result(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt",required=True)
    parser.add_argument("--output",required=True)
    args = parser.parse_args()
    report = build_report(args.attempt)
    result = saved_result(args.attempt,report)
    report["physical_checks"] = result["physical_checks"]
    report["realized_observables"] = result["realized_observables"]
    with (Path(args.attempt)/"result.json").open("x") as stream:
        stream.write(json.dumps(result,indent=2,allow_nan=False)+"\n")
    Path(args.output).write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")


if __name__ == "__main__":
    main()
