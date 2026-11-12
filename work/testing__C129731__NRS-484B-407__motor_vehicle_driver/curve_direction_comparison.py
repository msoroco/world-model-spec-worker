"""Independent source audit for paired exact curve sight directions."""

import hashlib
import json
import math
from pathlib import Path

from build_curve_opendrive import check_source_geometry, lane_position

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SHORT = {"short_of_500ft": ("short", [150.0, 150.125], False),
         "at_500ft": ("at", [152.4, 152.4], True),
         "beyond_500ft": ("beyond", [160.0, 160.125], True)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    if not Path(path).is_file():
        raise ValueError("Missing curve source: " + str(path))
    return json.loads(Path(path).read_text())


def rows(path):
    if not Path(path).is_file():
        raise ValueError("Missing curve source: " + str(path))
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def inspect(probe, direction, attempt):
    short, bracket, is_clear = SHORT[probe]
    name = "canonical-curve-" + short + "-" + ("a" if direction == "approach_a" else "b")
    case_id = HERE.name + "__curve__" + probe + "__occluded_" + direction
    attempt = Path(attempt)
    config, result = read(attempt / "config.json"), read(attempt / "result.json")
    if (config.get("selected_case_id") != case_id or result.get("case_id") != case_id or
            (config.get("rate_hz"), config.get("duration_s")) != (20, 55) or
            result.get("physical_acceptance_claimed") is not False or
            result.get("provenance_kind") != "synthetic_fixture"):
        raise ValueError("Curve exact identity/capture differs: " + name)
    site_name = "diagnostic-site" + ("" if short == "short" else "-" + short) + ".json"
    required = ("config.json", site_name, "motion_history.jsonl", "video_frames.jsonl",
                "trace.jsonl", "capture/evidence.jsonl", "turn_history.jsonl", "curve_context.json")
    hashes = result.get("source_evidence_hashes", {})
    for source in required:
        if hashes.get(source) != sha(attempt / source):
            raise ValueError("Sealed curve comparison source changed: " + source)
    site = read(attempt / site_name)
    build = read(HERE / ("branch-proof-" + name) / "build-receipt.json")
    if (config["site_source"]["sha256"] != sha(attempt / site_name) or
            build["site_sha256"] != config["site_source"]["sha256"] or
            site["source_status"] != "diagnostic_fixture" or
            site["map_source"]["status"] != "cpu_geometry_plan_unverified_in_carla" or
            site["occluder"]["target_direction"] != direction or
            build["occluded_direction"] != direction):
        raise ValueError("Curve direction/source binding differs")
    road = HERE / "native-map-plan/curve-road.xodr"
    check_source_geometry(road.read_text(), site)
    if build["source_road_sha256"] != sha(road):
        raise ValueError("Curve road hash differs")
    context = read(attempt / "curve_context.json")
    if (context["site_source_sha256"] != config["site_source"]["sha256"] or
            context["incoming_lanes"] != site["incoming_lanes"] or
            context["turn_site_xyz_m"] != site["turn_site_xyz_m"]):
        raise ValueError("Curve context/site binding differs")
    frame = rows(attempt / "video_frames.jsonl")
    motion = rows(attempt / "motion_history.jsonl")
    trace = rows(attempt / "trace.jsonl")
    rays = rows(attempt / "capture/evidence.jsonl")
    turns = rows(attempt / "turn_history.jsonl")
    if any(len(group) != 1100 for group in (frame, motion, trace, rays, turns)):
        raise ValueError("Curve original duration differs")
    lane_ids = {site["incoming_lanes"][name]["lane_id"] for name in ("approach_a", "approach_b")}
    blocked_lane = site["incoming_lanes"][direction]["lane_id"]
    fixed_motion, fixed_rays = [], []
    for index, (mapping, actors, tick, ray, turn) in enumerate(zip(frame, motion, trace, rays, turns)):
        native, time = mapping["native_frame"], mapping["time_s"]
        if (mapping["video_frame"] != index or actors["video_frame"] != index or
                actors["native_frame"] != native or tick["frame"] != native or
                ray["original_frame"] != native or turn["frame"] != native or
                actors["site_source_sha256"] != config["site_source"]["sha256"] or
                any(not math.isclose(value, time, abs_tol=.001) for value in
                    (tick["time_s"], ray["recording_time_s"], turn["time_s"])) or
                not math.isclose(time - frame[0]["time_s"], index / 20, abs_tol=.005)):
            raise ValueError("Curve original frame/time join differs")
        if set(actors["approaches"]) != {"approach_a", "approach_b"}:
            raise ValueError("Both curve approach actors required")
        for label, actor in actors["approaches"].items():
            lane = site["incoming_lanes"][label]
            if actor["road_lane"] != [lane["road_id"], lane["lane_id"]]:
                raise ValueError("Curve actor lane differs")
        vis = ray["visibility"]
        if vis["probe_distance_m"] != 152.4 or set(vis["required_lane_ids"]) != lane_ids:
            raise ValueError("Curve original ray inventory differs")
        by_lane = {item["lane_id"]: item for item in vis["approaches"]}
        if set(by_lane) != lane_ids:
            raise ValueError("Both curve approach rays required")
        blocked, clear = by_lane[blocked_lane], by_lane[next(iter(lane_ids - {blocked_lane}))]
        if (blocked["any_body_sight_horizon"]["bound"] != "first_sampled_occlusion" or
                blocked["any_body_sight_horizon"]["bracket_m"] != bracket or
                blocked["any_sample_clear_at_probe"] is not is_clear or
                clear["any_body_sight_horizon"]["bound"] != "at_least" or
                clear["any_sample_clear_at_probe"] is not True):
            raise ValueError("Curve direction-specific ray differs")
        normalized_actors = dict(actors)
        normalized_actors.pop("site_source_sha256")
        fixed_motion.append(normalized_actors)
        normalized_ray = copy_ray = dict(ray)
        normalized_ray["visibility"] = dict(ray["visibility"])
        normalized_ray["visibility"].pop("approaches")
        fixed_rays.append(normalized_ray)
    fixed_config = {key: value for key, value in config.items() if key not in
                    ("site_source", "selected_case_id", "supported_case_ids")}
    fixed_site = {key: value for key, value in site.items() if key != "occluder"}
    return {"name": name, "case_id": case_id, "direction": direction,
            "fixed_config": fixed_config, "fixed_site": fixed_site,
            "fixed_motion": fixed_motion, "fixed_rays": fixed_rays,
            "source_sha256": {source: hashes[source] for source in required}}


def audit(probe, attempts):
    if set(attempts) != {"approach_a", "approach_b"}:
        raise ValueError("Two exact curve direction attempts required")
    views = {direction: inspect(probe, direction, attempts[direction])
             for direction in ("approach_a", "approach_b")}
    a, b = views["approach_a"], views["approach_b"]
    for key in ("fixed_config", "fixed_site", "fixed_motion", "fixed_rays"):
        if a[key] != b[key]:
            raise ValueError("Unrelated curve comparison source condition differs: " + key)
    return {"format": "worker-curve-exact-comparison-diagnostic",
            "comparison_id": "curve_" + SHORT[probe][0] + "_approach_direction",
            "case_ids": [a["case_id"], b["case_id"]],
            "deliberate_difference": "occluded_direction",
            "source_sha256": {direction: views[direction]["source_sha256"]
                              for direction in views},
            "software_checks_passed": True, "passed": False,
            "physical_acceptance_claimed": False,
            "limitations": ["Synthetic rays and road do not prove physical occlusion or driver recognition"]}
