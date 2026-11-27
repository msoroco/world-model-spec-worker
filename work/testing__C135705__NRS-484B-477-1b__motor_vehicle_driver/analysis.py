"""Saved-only original alley-width finalizer, without a statutory verdict."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from width_measurement import FEET_PER_M, continuous_free_width_m, measure_saved

VIEWS=("overview","approach","reference_corner","driver_reference")


def measure_alley_width(source, case_id, frame_count):
    return measure_saved(source,case_id,expected_frames=frame_count)


def _rows(path):
    if not path.is_file():
        raise ValueError("Missing required source: "+path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def build(attempt):
    attempt=Path(attempt)
    config=json.loads((attempt/"config.json").read_text())
    construction=json.loads((attempt/"construction.json").read_text())
    source=attempt/"original-attempt"
    inventory=json.loads((source/"inventory.json").read_text())
    if (attempt/"fixture-provenance.json").exists():
        marker=json.loads((attempt/"fixture-provenance.json").read_text())
        if marker.get("diagnostic_fixture") is not True or marker.get("physical_acceptance_claimed") is not False or inventory.get("diagnostic_fixture") is not True:
            raise ValueError("untrusted diagnostic alley-width provenance")
    elif inventory.get("diagnostic_fixture") is not False:
        raise ValueError("original Native alley-width provenance missing")
    for name in ("frame_map.json", "alley_geometry.json", "width_history.json"):
        if not (source/name).is_file():
            raise ValueError("Missing required source: original-attempt/"+name)
    case_id=config["selected_case_id"]
    frame_count=inventory.get("frame_count")
    if frame_count!=900 and not (inventory.get("diagnostic_fixture") is True and frame_count==9):
        raise ValueError("original alley-width frame count invalid")
    measured=measure_alley_width(source,case_id,frame_count)
    frames=_rows(attempt/"video_frames.jsonl")
    trace=_rows(attempt/"trace.jsonl")
    original=json.loads((source/"frame_map.json").read_text())["frames"]
    history=json.loads((source/"width_history.json").read_text())["samples"]
    if len(frames)!=frame_count or len(trace)!=frame_count or len(original)!=frame_count or len(history)!=frame_count:
        raise ValueError("original full alley-width episode incomplete")
    for i,(row,src) in enumerate(zip(frames,original)):
        if row.get("video_frame")!=i or row.get("carla_frame")!=src["frame"] or row.get("time_s")!=src["time_s"] or trace[i].get("frame")!=src["frame"]:
            raise ValueError("original alley-width video/trace/frame join differs")
    for view in VIEWS:
        if not (attempt/(view+".mkv")).is_file():
            raise ValueError("Missing required source: "+view+".mkv")
    source_hashes={"original-attempt/"+name+".json":inventory["sources"][name]["sha256"]
                   for name in ("frame_map","alley_geometry","width_history")}
    plan=json.loads((attempt/"case-plan.json").read_text())
    measurements={}
    for disposition in plan["requirement_dispositions"]:
        if case_id in disposition["case_ids"]:
            key="alley_width_requirement_"+str(disposition["disposition_index"])
            measurements[key]={"value":{"minimum_available_continuous_width_ft":measured["minimum_available_continuous_width_ft"],
                "statutory_less_than_10_ft_observed":measured["statutory_less_than_10_ft_observed"],
                "held_samples":len(measured["held_samples"]),
                "alley_kind":measured["source_classification"],
                "ordinance_status":measured["ordinance_status"],
                "free_vehicular_movement_judgment":"unresolved",
                "ordinance_applicability_judgment":"unresolved"},
                "method":"measure_alley_width","sources":source_hashes}
    report={"format":"worker-analysis-report","measurements":measurements,
            "analysis_complete":True,"legal_verdict_claimed":False,
            "limitations":["Continuous free width is physical geometry; free vehicular movement remains independently reviewed.",
                           "The ordinance exception and qualifying other-alley status require original source review."]}
    return report,measured,frames,history,inventory,construction,config


def save_result(attempt,built):
    from worker_exchange.native_output import validate_result
    report,measured,frames,history,inventory,construction,config=built
    attempt=Path(attempt)
    channel_dir=attempt/"channels"
    channel_dir.mkdir(exist_ok=False)
    sample_by_frame={row["frame"]:row for row in measured["held_samples"]}
    geometry=json.loads((attempt/"original-attempt"/"alley_geometry.json").read_text())
    all_frame_widths={row['frame']:min(continuous_free_width_m(
        section['left_xy_m'],section['right_xy_m'],
        [row['ego_body_polygon_m'],*row.get('other_body_polygons_m',[])])*FEET_PER_M
        for section in geometry['cross_sections']) for row in history}
    values={
        "qualifying_other_alley":[{"alley_kind":geometry["alley_kind"],"public_highway":geometry["public_highway_status"]}]*len(frames),
        "local_ordinance_applicability":[geometry["ordinance_status"]]*len(frames),
        "original_vehicle_footprints":[{"ego":row["ego_body_polygon_m"],"other":row.get("other_body_polygons_m",[])} for row in history],
        "alley_cross_sections":[geometry["cross_sections"]]*len(frames),
        "available_continuous_width_ft":[round(all_frame_widths[row["carla_frame"]],6) for row in frames],
        "parking_activity":[{"phase":row.get("phase"),"speed_mps":row.get("speed_mps"),"controls":row.get("controls")} for row in history],
        "free_vehicular_movement":[{"other_vehicle_count":len(row.get("other_body_polygons_m",[])),"judgment":"unresolved"} for row in history],
        "four_view_frame_join":frames}
    evidence=[]
    for channel in construction["recording_description"]["channels"]:
        name=channel["name"]
        if name not in values:
            raise ValueError("uncaptured alley-width channel: "+name)
        path=channel_dir/(name+".jsonl")
        with path.open("x") as stream:
            for frame,value in zip(frames,values[name]):
                stream.write(json.dumps({"time_s":frame["time_s"],"value":value})+"\n")
        evidence.append({"name":name,"unit":channel["unit"],"reference":str(path.relative_to(attempt))})
    context=channel_dir/"context.json"
    context.write_text(json.dumps({"reviewed_alley_width_packet":{
        "geometry_sha256":inventory["sources"]["alley_geometry"]["sha256"],
        "map_sha256":inventory["map_sha256"],"legal_review":"pending"}})+"\n")
    for item in construction["recording_description"].get("context_inputs",[]):
        evidence.append({"name":item["name"],"unit":item["unit"],"reference":str(context.relative_to(attempt))})
    requested=config["variant"]
    planned=config.get("target_width_ft")
    observed=measured["minimum_available_continuous_width_ft"]
    matched=planned is not None and abs(observed-planned)<=0.25
    result={"case_id":config["selected_case_id"],
            "measured_values":{key:item["value"] for key,item in report["measurements"].items()},
            "target_checks":[{"target":"original continuous available width across parked alley",
                              "requested":planned if planned is not None else requested,"measured":observed,
                              "method":"measure_saved","tolerance":0.25 if planned is not None else None,
                              "matched":matched,"physical_cause_confirmed":False,
                              "cause_evidence":next(iter(report["measurements"].values()))["sources"]}],
            "setup_confirmed":True,"behavior_attempted":bool(measured["held_samples"]),
            "maneuver_completed":bool(measured["held_samples"]),
            "termination_reason":"Saved original alley width awaits physical, ordinance and legal review",
            "physical_failure_flags":[],"trace_reference":"trace.jsonl",
            "video_references":[view+".mkv" for view in VIEWS],
            "video_frame_map_reference":"video_frames.jsonl",
            "recording_description":construction["recording_description"],
            "recording_evidence":evidence,
            "realized_observables":{"available_continuous_width_ft":{"value":observed,"unit":"ft",
                "method":"original surveyed cross-section minus original body polygons",
                "time_window":"parked hold","statistic":"minimum",
                "reference":"channels/available_continuous_width_ft.jsonl",
                "source_refs":next(iter(report["measurements"].values()))["sources"]}},
            "physical_checks":{"setup":{"status":"unverified","reason":"original qualifying alley and ordinance review pending"},
                               "target":{"status":"met" if matched else "unverified","reason":"engineering width target only"},
                               "maneuver":{"status":"unverified","reason":"actual free vehicular movement review pending"}},
            "provenance_kind":"synthetic_fixture" if inventory["diagnostic_fixture"] else "native",
            "diagnostic_fixture":inventory["diagnostic_fixture"],
            "physical_acceptance_claimed":False}
    validate_result(result)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--attempt",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args()
    if (args.attempt/"result.json").exists() or args.output.exists():
        raise ValueError("refusing to replace original saved analysis")
    built=build(args.attempt)
    result=save_result(args.attempt,built)
    report=built[0]
    report["physical_checks"]=result["physical_checks"]
    report["realized_observables"]=result["realized_observables"]
    (args.attempt/"result.json").write_text(json.dumps(result,indent=2)+"\n")
    args.output.write_text(json.dumps(report,indent=2)+"\n")


if __name__=="__main__":main()
