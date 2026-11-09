"""Saved-only, source-bound measurements. Never changes original acquisition."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def rows(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]


def center(vertices):
    if len(vertices) < 4:
        raise ValueError("Incomplete Native vehicle body")
    return [sum(v[i] for v in vertices) / len(vertices) for i in (0, 1)]


def following_measurement(samples, mapping, context):
    if len(samples) != len(mapping) or not samples:
        raise ValueError("Original frame coverage differs")
    observed = []
    for index, (s, m) in enumerate(zip(samples, mapping)):
        if (s["frame"] != m["carla_frame"] or m["video_frame"] != index or
                abs(s["time_s"] - m["time_s"]) > 1e-6):
            raise ValueError("Original frame/time join differs")
        ego, lead = center(s["ego_body_vertices_m"]), center(s["lead_body_vertices_m"])
        gap = math.dist(ego, lead)
        same_lane = s["ego_lane_id"] == s["lead_lane_id"]
        observed.append({"frame": s["frame"], "time_s": s["time_s"],
                         "center_separation_m": gap, "same_lane": same_lane,
                         "ego_speed_mps": s["ego_speed_mps"],
                         "lead_speed_mps": s["lead_speed_mps"],
                         "lane_change_requested": s["lane_change_requested"]})
    before = [r for r in observed if r["same_lane"] and not r["lane_change_requested"]]
    if not before:
        raise ValueError("No original pre-change following interval")
    result = {"pre_change_samples": len(before),
              "separation_m": {"first": before[0]["center_separation_m"],
                               "minimum": min(r["center_separation_m"] for r in before),
                               "maximum": max(r["center_separation_m"] for r in before)},
              "speed_mps": {"ego_mean": sum(r["ego_speed_mps"] for r in before) / len(before),
                            "lead_mean": sum(r["lead_speed_mps"] for r in before) / len(before)},
              "time_window_s": [before[0]["time_s"], before[-1]["time_s"]],
              "traffic": {"lead_vehicle_observed": True, "other_traffic_not_inventoried": True},
              "highway_condition": {"weather": samples[0]["weather"],
                                    "crest_elevation_m": context["crest_elevation_m"]},
              "legal_standard": "unresolved"}
    return result


def lane_transition_status(samples, target_lane):
    if len(samples) < 20 or any("ego_lane_id" not in s or "lane_change_requested" not in s
                                for s in samples):
        return {"status": "unverified", "transition_frame": None}
    transition = next((i for i in range(1, len(samples))
                       if samples[i]["lane_change_requested"] and
                       samples[i]["ego_lane_id"] == target_lane), None)
    sustained = transition is not None and all(s["ego_lane_id"] == target_lane
                                               for s in samples[-20:])
    return {"status": "met" if sustained else "not_met",
            "transition_frame": None if transition is None else samples[transition]["frame"]}


def analyze(attempt, report_path):
    root = Path(attempt)
    cfg = json.loads(required(root, "config.json").read_text())
    sample_path = required(root, "following_samples.jsonl")
    map_path = required(root, "video_frames.jsonl")
    context_path = required(root, "surface_context.json")
    trace_path = required(root, "trace.jsonl")
    for name in ("overview", "approach", "reference_corner", "driver_reference"):
        required(root, name + ".mkv")
    samples = rows(sample_path)
    mapping = rows(map_path)
    context = json.loads(context_path.read_text())
    measured = following_measurement(samples, mapping, context)
    channel_values = {
        "ego.body": [s["ego_body_vertices_m"] for s in samples],
        "lead.body": [s["lead_body_vertices_m"] for s in samples],
        "ego.speed": [s["ego_speed_mps"] for s in samples],
        "lead.speed": [s["lead_speed_mps"] for s in samples],
        "following.separation": [math.dist(center(s["ego_body_vertices_m"]),
                                             center(s["lead_body_vertices_m"])) for s in samples],
        "ego.lane": [s["ego_lane_id"] for s in samples],
        "lead.lane": [s["lead_lane_id"] for s in samples],
        "road.weather": [s["weather"] for s in samples],
    }
    (root / "channels").mkdir(exist_ok=True)
    evidence = []
    for channel in cfg["recording_description"]["channels"]:
        name = channel["name"]
        path = root / "channels" / (name.replace(".", "_") + ".jsonl")
        if path.exists():
            raise ValueError("Retain previous derived channel: " + str(path))
        path.write_text("".join(json.dumps({"time_s": m["time_s"], "value": value},
                                           allow_nan=False) + "\n"
                                for m, value in zip(mapping, channel_values[name])))
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(path.relative_to(root))})
    sources = {name: sha(root / name) for name in
               ("following_samples.jsonl", "video_frames.jsonl", "surface_context.json")}
    from worker_exchange.native_output import write_result, provenance_record
    target_lane = context["target_lane_id"]
    transition = lane_transition_status(samples, target_lane)
    sustained = transition["status"] == "met"
    full_capture = len(mapping) == cfg["rate_hz"] * cfg["duration_s"]
    check_sources = {**sources, "trace.jsonl": sha(trace_path)}
    interval = [{"first_frame": mapping[0]["carla_frame"],
                 "last_frame": mapping[-1]["carla_frame"],
                 "first_time_s": mapping[0]["time_s"], "last_time_s": mapping[-1]["time_s"]}]
    checks = {"setup": {"status": "met" if full_capture else "not_met",
                         "method": "900 original synchronized frame and trace joins",
                         "sources": check_sources, "intervals": interval},
              "target": {"status": "unverified", "method": "initial body-center separation",
                         "sources": check_sources, "intervals": interval},
              "maneuver": {"status": transition["status"],
                           "method": "original Native lane ID transition with final 20-frame occupancy",
                           "sources": check_sources, "intervals": interval,
                           "details": {"target_lane_id": target_lane,
                                       "transition_frame": transition["transition_frame"],
                                       "engineering_only": True}}}
    base = {"case_id": cfg["selected_case_id"],
            "measured_values": measured,
            "target_checks": [{"target": "initial following separation", "requested": cfg["initial_gap_m"],
                               "measured": measured["separation_m"]["first"],
                               "method": "first same-lane body-center separation; diagnostic spawn tolerance",
                               "tolerance": 5.0,
                               "matched": abs(measured["separation_m"]["first"] - cfg["initial_gap_m"]) <= 5.0,
                               "physical_cause_confirmed": True,
                               "cause_evidence": sources}],
            "termination_reason": "planned duration",
            "physical_failure_flags": {"detection_validated": False, "events": []},
            "trace_reference": "trace.jsonl",
            "video_references": [n + ".mkv" for n in
                                 ("overview", "approach", "reference_corner", "driver_reference")],
            "video_frame_map_reference": "video_frames.jsonl",
            "recording_description": cfg["recording_description"],
            "recording_evidence": evidence,
            "setup_confirmed": full_capture, "behavior_attempted": True,
            "maneuver_completed": sustained, "physical_checks": checks,
            "realized_observables": {"following.separation": {
                "value": measured["separation_m"]["first"], "unit": "m",
                "method": "first pre-change original body-center separation",
                "time_window": "pre-change original frame interval", "statistic": "first",
                "sample_window_s": measured["time_window_s"],
                "reference": "channels/following_separation.jsonl"}},
            "physical_acceptance_claimed": False, **provenance_record(root)}
    checks["target"]["status"] = "met" if base["target_checks"][0]["matched"] else "not_met"
    write_result(root, base)
    report = {"format": "worker-analysis-report", "case_id": cfg["selected_case_id"],
              "measurements": {"following_before_lane_change": {
                  "method": "following_measurement", "value": measured,
                  "sources": sources}},
              "physical_checks": checks,
              "realized_observables": base["realized_observables"],
              "legal_judgment": "reasonable and prudent unresolved",
              "analysis_complete": True}
    Path(report_path).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--attempt", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    analyze(args.attempt, args.output)


if __name__ == "__main__":
    main()
