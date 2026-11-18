"""Observe active controlling traffic signal at signed-entrance ego entry.

An illuminated light elsewhere at the junction is insufficient. The output
preserves control and timing facts without a legal exception conclusion.
"""

import hashlib
import json
import math
import argparse
import subprocess
from pathlib import Path

from shapely.geometry import LineString, MultiPoint, Polygon


REQUIRED=("signal_context.json","signal_history.jsonl","video_frames.jsonl")
CAMERAS=("overview","approach","reference_corner","driver_reference")


def _number(value,label):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError("Missing finite "+label)
    return float(value)


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(root:Path)->dict:
    root=Path(root);hashes={}
    for name in REQUIRED:
        path=root/name
        if not path.is_file():raise ValueError("Missing original source: "+name)
        hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    ctx=json.loads((root/"signal_context.json").read_text())
    for key in ("native_map_id","intersection_id","ego_road_id","ego_lane_id",
                "native_signal_id","affected_lane_source","signal_head_video_source",
                "signed_entrance_source","junction_source"):
        if ctx.get(key) is None:raise ValueError("Missing sourced signal context: "+key)
    polygon=Polygon(ctx.get("intersection_polygon_xy_m",[]))
    if not polygon.is_valid or polygon.area<=0:raise ValueError("Invalid intersection polygon")
    route=ctx.get("ego_route_lanes")
    if (not isinstance(route,list) or not route or route[0]!=[ctx["ego_road_id"],ctx["ego_lane_id"]]):
        raise ValueError("Missing sourced ego approach route")
    rows,frames=_rows(root/"signal_history.jsonl"),_rows(root/"video_frames.jsonl")
    if len(rows)<3 or len(rows)!=len(frames):raise ValueError("Incomplete signal/ego history")
    previous=(-1,-math.inf);samples=[];first_entry=None
    for i,(row,frame) in enumerate(zip(rows,frames)):
        fid,time=row.get("frame"),_number(row.get("time_s"),"time")
        if type(fid) is not int or fid<=previous[0] or time<=previous[1]:
            raise ValueError("Nonmonotone original history")
        previous=fid,time
        if frame.get("video_frame")!=i or frame.get("carla_frame")!=fid or frame.get("time_s")!=time:
            raise ValueError("Original frame join failed")
        camera_frames=frame.get("camera_frames")
        if (not isinstance(camera_frames,dict) or set(camera_frames)!=set(CAMERAS) or
                any(camera_frames[name]!=fid for name in CAMERAS)):
            raise ValueError("Four original camera frame joins required")
        if row.get("native_signal_id")!=ctx["native_signal_id"]:
            raise ValueError("Native governing light identity mismatch")
        observed_lane=[row.get("ego_road_id"),row.get("ego_lane_id")]
        if observed_lane not in route or (i==0 and observed_lane!=route[0]):
            raise ValueError("Ego outside sourced signal route")
        state=row.get("signal_state")
        if state not in ("Red","Yellow","Green","Off"):
            raise ValueError("Signal state missing")
        controls=row.get("signal_controls_ego")
        if type(controls) is not bool:raise ValueError("Missing affected-lane control observation")
        speed=_number(row.get("ego_speed_mps"),"ego speed")
        if speed<0:raise ValueError("Negative speed")
        vertices=row.get("ego_body_vertices_xy_m")
        if not isinstance(vertices,list) or len(vertices)<4:raise ValueError("Missing complete ego body")
        body=MultiPoint([(_number(p[0],"body x"),_number(p[1],"body y")) for p in vertices]).convex_hull
        inside=body.intersects(polygon)
        if i==0 and inside:raise ValueError("Missing pre-entry approach")
        if inside and first_entry is None:
            first_entry={"frame":fid,"time_s":time,"signal_state":state,
                         "signal_controls_ego":controls}
        samples.append({"frame":fid,"time_s":time,"signal_state":state,
                        "signal_controls_ego":controls,"ego_speed_mps":speed,
                        "ego_body_in_intersection":inside})
    if first_entry is None:raise ValueError("No observed ego entry")
    active=first_entry["signal_controls_ego"] and first_entry["signal_state"]!="Off"
    return {"format":"worker-controlling-signal-exception-observations","sources":hashes,
            "first_ego_entry":first_entry,"operative_signal_controls_ego_at_entry_observed":active,
            "samples":samples,"official_control_judgment":"unresolved pending source review",
            "legal_exception_judgment":"unresolved","legal_conclusion":"unresolved"}


def measure_operative_signal_at_entry(report):
    return report["operative_signal_controls_ego_at_entry_observed"]


def measure_entry_signal_state(report):
    return report["first_ego_entry"]["signal_state"]


def validate_saved_site_binding(config, context, control):
    """Reject a source history from a different configured Native site."""
    site = config.get("site")
    if not isinstance(site, dict) or site.get("native_map_id") != context.get("native_map_id"):
        raise ValueError("Saved site map differs from exact construction")
    lanes = site.get("approach_lanes", {})
    if (lanes.get("ego") != [context.get("ego_road_id"), context.get("ego_lane_id")] or
            lanes.get("through") != [context.get("through_road_id"), context.get("through_lane_id")] or
            context.get("ego_route_lanes", [None])[0] != lanes.get("ego") or
            context.get("through_route_lanes", [None])[0] != lanes.get("through")):
        raise ValueError("Saved approach lanes differ from exact construction")
    if (control.get("native_map_id") != site["native_map_id"] or
            control.get("intersection_xy_m") != context.get("intersection_polygon_xy_m") or
            control.get("intersection_id") != context.get("intersection_id")):
        raise ValueError("Saved control geometry differs from exact construction")


def measure_yield_baseline(attempt, context, interaction, frames, review):
    """Retain the yield reference and through traffic facts without judging hazard."""
    source = attempt/"yield_context.json"
    if not source.is_file():
        raise ValueError("Missing required source: yield_context.json")
    baseline = json.loads(source.read_text())
    if review.get("yield_context_sha256") != hashlib.sha256(source.read_bytes()).hexdigest():
        raise ValueError("Original-camera review yield context hash differs")
    if (baseline.get("native_map_id") != context["native_map_id"] or
            baseline.get("intersection_id") != context["intersection_id"] or
            baseline.get("ego_approach_lane") != [context["ego_road_id"], context["ego_lane_id"]] or
            baseline.get("through_highway_lane") != [context.get("through_road_id"), context.get("through_lane_id")]):
        raise ValueError("Yield reference differs from original signed intersection")
    if (baseline.get("stop_line_present") is not False or
            baseline.get("near_crosswalk_present") is not False or
            baseline.get("sign_type") != "yield" or
            not isinstance(baseline.get("source_description"), str) or
            not baseline["source_description"].strip()):
        raise ValueError("Nearest-view yield reference lacks sourced hierarchy")
    observations = review["observations"]
    for key in ("yield_sign_visible", "no_stop_line_visible", "no_near_crosswalk_visible",
                "nearest_view_reference_reviewed"):
        if observations.get(key) is not True:
            raise ValueError("Yield hierarchy lacks original-camera review: " + key)
    if observations.get("officer_control_observed") is not False:
        raise ValueError("Yield baseline requires reviewed absence of officer control")
    points = baseline.get("nearest_view_line_xy_m")
    if (not isinstance(points, list) or len(points) != 2 or
            any(not isinstance(p, list) or len(p) != 2 for p in points)):
        raise ValueError("Missing sourced nearest-view line")
    line = LineString([(_number(p[0], "reference x"), _number(p[1], "reference y"))
                       for p in points])
    if line.length <= 0:
        raise ValueError("Degenerate nearest-view line")
    polygon = Polygon(context["intersection_polygon_xy_m"])
    if line.intersects(polygon):
        raise ValueError("Nearest-view reference lies inside intersection")
    first_reference = None
    first_entry = None
    through_at_entry = None
    through_route = context.get("through_route_lanes")
    if (not isinstance(through_route, list) or not through_route or
            through_route[0] != baseline["through_highway_lane"]):
        raise ValueError("Missing sourced through-highway route")
    for frame, bodies in zip(frames, interaction):
        if ([bodies["ego"].get("road_id"), bodies["ego"].get("lane_id")] not in
                context["ego_route_lanes"] or
                [bodies["through"].get("road_id"), bodies["through"].get("lane_id")] not in
                through_route):
            raise ValueError("Original body left sourced yield/highway route")
        ego = MultiPoint([(_number(p[0], "ego body x"), _number(p[1], "ego body y"))
                          for p in bodies["ego"]["body_vertices_m"]]).convex_hull
        through = MultiPoint([(_number(p[0], "through body x"), _number(p[1], "through body y"))
                              for p in bodies["through"]["body_vertices_m"]]).convex_hull
        if first_reference is None and ego.intersects(line):
            first_reference = frame["carla_frame"]
        if first_entry is None and ego.intersects(polygon):
            first_entry = frame["carla_frame"]
            through_at_entry = through.intersects(polygon)
    if first_reference is None or first_entry is None or first_reference >= first_entry:
        raise ValueError("Original ego body did not cross nearest-view reference before entry")
    return {"nearest_view_reference_frame": first_reference,
            "first_ego_entry_frame": first_entry,
            "through_body_in_intersection_at_entry": through_at_entry,
            "immediate_hazard_judgment": "unresolved",
            "right_of_way_judgment": "unresolved",
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}


def audit_signal_comparison(left, right, comparison_id):
    """Independently verify fixed source conditions and the declared signal difference."""
    if comparison_id not in ("signal_exception_control", "signal_exception_state"):
        raise ValueError("Unknown exact signal comparison")
    records = []
    for root in (Path(left), Path(right)):
        config = json.loads((root/"config.json").read_text())
        case_id = config.get("selected_case_id")
        report = analyze(root)
        frames = _rows(root/"video_frames.jsonl")
        review = validate_source_camera_review(root, frames, case_id)
        context = json.loads((root/"signal_context.json").read_text())
        records.append((case_id, report, review, context))
    first, second = records
    prefix = "testing__C158196__NRS-484B-257-1__motor_vehicle_driver__"
    expected = {
        "signal_exception_control": ("signal_controls_ego", "signal_visible_not_governing"),
        "signal_exception_state": ("signal_controls_ego", "signal_off")}
    if tuple(row[0] for row in records) != tuple(prefix+name for name in expected[comparison_id]):
        raise ValueError("Comparison selects different exact cases")
    fixed = ("native_map_id", "intersection_id", "ego_road_id", "ego_lane_id",
             "ego_route_lanes", "intersection_polygon_xy_m", "signed_entrance_source",
             "junction_source", "through_road_id", "through_lane_id", "through_route_lanes")
    if any(first[3].get(key) != second[3].get(key) for key in fixed):
        raise ValueError("Comparison changed fixed signed intersection or routes")
    profiles = []
    for root in (Path(left), Path(right)):
        streams = []
        for name in CAMERAS:
            probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                    "-show_entries", "stream=width,height,r_frame_rate",
                                    "-of", "json", str(root/(name+".mkv"))],
                                   capture_output=True, text=True, check=True)
            streams.append(json.loads(probe.stdout)["streams"][0])
        profiles.append(streams)
    if profiles[0] != profiles[1]:
        raise ValueError("Comparison changed fixed four-camera capture profile")
    if not all(row[2]["observations"]["signed_entrance_visible"] for row in records):
        raise ValueError("Comparison lacks reviewed signed entrance")
    entry_a, entry_b = first[1]["first_ego_entry"], second[1]["first_ego_entry"]
    if comparison_id == "signal_exception_control":
        if (not entry_a["signal_controls_ego"] or entry_b["signal_controls_ego"] or
                entry_a["signal_state"] != entry_b["signal_state"] or
                entry_a["signal_state"] == "Off" or
                first[3]["native_signal_id"] == second[3]["native_signal_id"]):
            raise ValueError("Comparison lacks isolated governing-head difference")
    else:
        if (not entry_a["signal_controls_ego"] or not entry_b["signal_controls_ego"] or
                entry_a["signal_state"] == "Off" or entry_b["signal_state"] != "Off" or
                first[3]["native_signal_id"] != second[3]["native_signal_id"] or
                first[3]["signal_head_video_source"] != second[3]["signal_head_video_source"]):
            raise ValueError("Comparison lacks isolated operative-state difference")
    return {"format":"worker-c158196-source-comparison-audit",
            "comparison_id":comparison_id,"case_ids":[first[0],second[0]],
            "fixed_conditions_checked":[*fixed,"four_camera_capture_profile"],
            "declared_difference_observed":True,
            "source_camera_reviews_checked":True,
            "physical_acceptance_claimed":False,"legal_conclusion":"unresolved"}


def validate_source_camera_review(attempt, frames, case_id):
    """Bind a separately recorded visual review to all four retained originals."""
    path = attempt/"signal_head_review.json"
    if not path.is_file():
        raise ValueError("Missing required source: signal_head_review.json")
    review = json.loads(path.read_text())
    if (review.get("method") != "original_source_camera_frame_review" or
            review.get("case_id") != case_id or
            not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip()):
        raise ValueError("Missing identified original-camera review")
    if review.get("reviewed_carla_frames") != [row["carla_frame"] for row in frames]:
        raise ValueError("Original-camera review frame coverage differs")
    sources = review.get("camera_sha256")
    if not isinstance(sources, dict) or set(sources) != set(CAMERAS):
        raise ValueError("Four original-camera review hashes required")
    for name in CAMERAS:
        if sources[name] != hashlib.sha256((attempt/(name+".mkv")).read_bytes()).hexdigest():
            raise ValueError("Original-camera review source hash differs: " + name)
        probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
                                "-select_streams", "v:0", "-show_entries",
                                "stream=codec_name,nb_read_frames", "-of", "json",
                                str(attempt/(name+".mkv"))], capture_output=True, text=True)
        if probe.returncode:
            raise ValueError("Original-camera source media unreadable: " + name)
        streams = json.loads(probe.stdout).get("streams", [])
        if (len(streams) != 1 or streams[0].get("codec_name") != "ffv1" or
                streams[0].get("nb_read_frames") != str(len(frames))):
            raise ValueError("Original-camera decoded frame count or codec differs: " + name)
    observations = review.get("observations")
    if not isinstance(observations, dict) or any(
            type(observations.get(key)) is not bool for key in
            ("signed_entrance_visible", "signal_head_visible", "head_at_ego_approach")):
        raise ValueError("Missing explicit original-camera visual observations")
    suffix = case_id.rsplit("__", 1)[-1]
    required_visual = {
        "signal_controls_ego": {"signed_entrance_visible": True,
                                "signal_head_visible": True,
                                "head_at_ego_approach": True},
        "signal_visible_not_governing": {"signed_entrance_visible": True,
                                         "signal_head_visible": True,
                                         "head_at_ego_approach": False},
        "signal_off": {"signed_entrance_visible": True,
                       "signal_head_visible": True,
                       "head_at_ego_approach": True},
        "yield_without_signal_control": {"signed_entrance_visible": True},
    }
    if suffix not in required_visual or any(
            observations[key] is not value for key, value in required_visual[suffix].items()):
        raise ValueError("Case-specific original-camera visual observations differ")
    return review


def finalize(attempt, output):
    """Derive primary signal-exception observations from retained originals."""
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt/"result.json").exists() or (attempt/"channels").exists():
        raise ValueError("Retain prior C158196 finalization; choose a fresh attempt")
    required = ("config.json", "road.xodr", "trace.jsonl", "capture/evidence.jsonl",
                "signal_context.json", "signal_history.jsonl", "interaction_history.jsonl",
                "control_context.json", "video_frames.jsonl", *(name+".mkv" for name in CAMERAS))
    for name in required:
        if not (attempt/name).is_file() or (attempt/name).stat().st_size == 0:
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt/"config.json").read_text())
    case_id = config.get("selected_case_id")
    prefix = "testing__C158196__NRS-484B-257-1__motor_vehicle_driver__"
    expected = {"signal_controls_ego": True, "signal_visible_not_governing": False,
                "signal_off": False, "yield_without_signal_control": False}
    if not isinstance(case_id, str) or not case_id.startswith(prefix) or case_id[len(prefix):] not in expected:
        raise ValueError("Wrong exact C158196 signal case")
    if config.get("law_id") != "NRS-484B-257-1" or config.get("cell_id") != "C158196":
        raise ValueError("Wrong law or cell identity")
    report = analyze(attempt)
    frames = _rows(attempt/"video_frames.jsonl")
    review = validate_source_camera_review(attempt, frames, case_id)
    trace = _rows(attempt/"trace.jsonl")
    interaction = _rows(attempt/"interaction_history.jsonl")
    evidence = _rows(attempt/"capture/evidence.jsonl")
    if (len(frames) != len(trace) or len(frames) != len(interaction) or
            len(frames) != len(evidence)):
        raise ValueError("Original trace, body, evidence and camera histories differ")
    for frame, motion, bodies, event in zip(frames, trace, interaction, evidence):
        fid = frame["carla_frame"]
        if (motion.get("frame") != fid or bodies.get("frame") != fid or
                event.get("original_frame") != fid or
                any(abs(row.get("time_s", -math.inf)-frame["time_s"]) > 1e-6
                    for row in (motion,bodies))):
            raise ValueError("Original trace, body or evidence frame join failed")
        for role in ("ego", "through"):
            body = bodies.get(role, {}).get("body_vertices_m")
            if not isinstance(body, list) or len(body) < 4:
                raise ValueError("Missing complete original interaction body: " + role)
    context = json.loads((attempt/"signal_context.json").read_text())
    control = json.loads((attempt/"control_context.json").read_text())
    validate_saved_site_binding(config, context, control)
    yield_baseline = None
    if case_id.endswith("__yield_without_signal_control"):
        yield_baseline = measure_yield_baseline(attempt, context, interaction, frames, review)
    channels = attempt/"channels"
    channels.mkdir()
    for name, values in {
        "operative_signal_control": [int(sample["signal_controls_ego"] and
                                         sample["signal_state"] != "Off") for sample in report["samples"]],
        "signal_state": [sample["signal_state"] for sample in report["samples"]],
        "ego_crossing_body": [row["ego"] for row in interaction],
    }.items():
        with (channels/(name+".jsonl")).open("x") as stream:
            for frame, value in zip(frames, values):
                stream.write(json.dumps({"original_frame":frame["carla_frame"],
                                         "time_s":frame["time_s"],"value":value},
                                        allow_nan=False)+"\n")
    observed = measure_operative_signal_at_entry(report)
    requested = expected[case_id[len(prefix):]]
    source_hashes = {name:hashlib.sha256((attempt/name).read_bytes()).hexdigest()
                     for name in (*required,"signal_head_review.json")}
    if yield_baseline is not None:
        source_hashes["yield_context.json"] = yield_baseline["source_sha256"]
    governance_review = {
        "native_signal_id": context["native_signal_id"],
        "ego_route_lanes": context["ego_route_lanes"],
        "through_route_lanes": context["through_route_lanes"],
        "entry_signal_state": measure_entry_signal_state(report),
        "operative_signal_controls_ego_at_entry_observed": observed,
        "original_camera_observations": review["observations"],
        "original_camera_sha256": review["camera_sha256"],
        "source_sha256": {name: source_hashes[name] for name in (
            "signal_context.json", "control_context.json", "signal_history.jsonl",
            "interaction_history.jsonl", "video_frames.jsonl", "signal_head_review.json")},
        "official_control_status": "unresolved",
    }
    yield_site_review = {
        "signed_entrance_source": context["signed_entrance_source"],
        "ego_route_lanes": context["ego_route_lanes"],
        "through_route_lanes": context["through_route_lanes"],
        "original_camera_observations": review["observations"],
        "yield_baseline": yield_baseline,
        "source_sha256": {name: source_hashes[name] for name in (
            "signal_context.json", "interaction_history.jsonl", "video_frames.jsonl",
            "signal_head_review.json")},
        "sign_propriety_and_right_of_way": "unresolved",
    }
    (attempt/"recording-context.json").write_text(json.dumps({
        "signal_governance_review": governance_review,
        "yield_site_review": yield_site_review,
    }, indent=2, allow_nan=False) + "\n")
    result = {"case_id":case_id,
              "measured_values":{"operative_signal_controls_ego_at_entry_observed":observed,
                                 "entry_signal_state":measure_entry_signal_state(report),
                                 "first_ego_entry":report["first_ego_entry"],
                                 "signal_governance_review":governance_review,
                                 "yield_site_review":yield_site_review},
              "target_checks":[{"target":"operative_signal_controls_ego_at_entry_observed",
                                "requested":requested,"measured":observed,
                                "method":"original affected-lane and signal-state join at complete body entry",
                                "tolerance":0,"matched":observed is requested,
                                "physical_cause_confirmed":False,
                                "cause_evidence":["signal_history.jsonl","signal_context.json",
                                                  "interaction_history.jsonl","video_frames.jsonl"]}],
              "setup_confirmed":False,"behavior_attempted":False,
              "maneuver_completed":False,
              "termination_reason":"Saved source analysis; physical and official control acceptance pending",
              "physical_failure_flags":["Official control, realized camera quality and legal exception remain unresolved"],
              "trace_reference":"trace.jsonl",
              "video_references":[name+".mkv" for name in CAMERAS],
              "video_frame_map_reference":"video_frames.jsonl",
              "recording_description":config["recording_description"],
              "recording_evidence":[{"name":name,"unit":unit,
                                      "reference":"channels/"+name+".jsonl"}
                                     for name,unit in (("operative_signal_control","count"),
                                                       ("signal_state","text"),
                                                       ("ego_crossing_body","structured record"))]
                                   + [{"name":name,"unit":"structured record",
                                       "reference":"recording-context.json"}
                                      for name in ("signal_governance_review","yield_site_review")],
              "source_evidence_hashes":source_hashes,"realized_observables":{}}
    if yield_baseline is not None:
        result["measured_values"]["yield_baseline"] = yield_baseline
    try:
        from worker_exchange.native_output import physical_result, write_result
    except ModuleNotFoundError:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]/"runtime/scenario_pipeline"))
        from worker_exchange.native_output import physical_result, write_result
    result = physical_result(attempt, result)
    write_result(attempt, result)
    analysis = {"format":"worker-c158196-signal-analysis","case_id":case_id,
                "measurements":{
                    "operative_signal_at_entry":{"value":observed,
                        "method":"measure_operative_signal_at_entry",
                        "sources":{name:source_hashes[name] for name in
                                   ("signal_context.json","signal_history.jsonl","video_frames.jsonl")}},
                    "entry_signal_state":{"value":measure_entry_signal_state(report),
                        "method":"measure_entry_signal_state",
                        "sources":{name:source_hashes[name] for name in
                                   ("signal_context.json","signal_history.jsonl","video_frames.jsonl")}}},
                "source_report":report,"source_camera_review":review,
                "yield_baseline":yield_baseline,
                "physical_checks":result["physical_checks"],
                "realized_observables":result["realized_observables"],
                "legal_conclusion":"unresolved","analysis_complete":True}
    output.write_text(json.dumps(analysis,indent=2,allow_nan=False)+"\n")
    return analysis


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--attempt",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    finalize(args.attempt,args.output)
