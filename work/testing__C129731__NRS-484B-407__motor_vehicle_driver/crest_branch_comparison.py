"""Independent source comparison for four crest placement/direction diagnostics."""

import hashlib
import json
import math
from pathlib import Path

from build_crest_opendrive import check_source_geometry, grade

HERE = Path(__file__).resolve().parent
CASE = HERE.name + "__crest__short_of_500ft"
NAMES = ("near-a", "near-b", "approach-a", "approach-b")
REQUIRED = ("config.json", "diagnostic-site-crest-short.json", "motion_history.jsonl",
            "video_frames.jsonl", "trace.jsonl", "capture/evidence.jsonl",
            "turn_history.jsonl", "curve_context.json")
PROBES = {"short_of_500ft": ("short", 150.0, [150.0, 150.125], False),
          "at_500ft": ("at", 152.4, [152.4, 152.4], True),
          "beyond_500ft": ("beyond", 160.0, [160.0, 160.125], True)}


def names_for(probe):
    suffix = PROBES[probe][0]
    return NAMES if suffix == "short" else tuple(suffix + "-" + name for name in NAMES)


def required_for(probe):
    suffix = PROBES[probe][0]
    return tuple(source.replace("crest-short", "crest-" + suffix) for source in REQUIRED)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing comparison source: " + str(path))
    return json.loads(path.read_text())


def rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing comparison source: " + str(path))
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def normalized_actor(actor, turn_x):
    xyz = actor["location_xyz_m"]
    return {"x_relative_to_turn_m": round(xyz[0] - turn_x, 7),
            "y_m": round(xyz[1], 7), "height_above_authored_grade_m": round(xyz[2] - grade(xyz[0]), 7),
            "yaw_deg": actor["yaw_deg"], "velocity_xyz_mps": actor["velocity_xyz_mps"],
            "road_lane": actor["road_lane"]}


def inspect(name, attempt, probe="short_of_500ft", canonical=False):
    branch_name = name.removeprefix("canonical-") if canonical else name
    if canonical and probe == "short_of_500ft":
        branch_name = branch_name.removeprefix("short-")
    if branch_name not in names_for(probe):
        raise ValueError("Unknown exact crest alternative")
    attempt = Path(attempt)
    config, result = read(attempt / "config.json"), read(attempt / "result.json")
    placement = "near_summit" if branch_name.endswith("near-a") or branch_name.endswith("near-b") else "approach_to_crest"
    direction = "approach_a" if branch_name.endswith("-a") else "approach_b"
    case = HERE.name + "__crest__" + probe
    if canonical:
        case += "__" + placement + "__occluded_" + direction
    if config.get("selected_case_id") != case or (config.get("rate_hz"), config.get("duration_s")) != (20, 55):
        raise ValueError("Crest branch capture contract changed")
    if result.get("case_id") != case or result.get("provenance_kind") != "synthetic_fixture" or result.get("physical_acceptance_claimed") is not False:
        raise ValueError("Crest branch diagnostic result identity differs")
    hashes = result.get("source_evidence_hashes", {})
    required = required_for(probe)
    site_name = "diagnostic-site-crest-" + PROBES[probe][0] + ".json"
    for source in required:
        if hashes.get(source) != sha(attempt / source):
            raise ValueError("Sealed comparison source changed: " + source)
    site = read(attempt / site_name)
    if config["site_source"]["sha256"] != sha(attempt / site_name):
        raise ValueError("Config/site source binding differs")
    build = read(HERE / ("branch-proof-" + name) / "build-receipt.json")
    if build["site_sha256"] != config["site_source"]["sha256"]:
        raise ValueError("Branch build/site source binding differs")
    if site["source_status"] != "diagnostic_fixture" or site["map_source"]["status"] != "cpu_geometry_plan_unverified_in_carla":
        raise ValueError("Branch falsely claims Native source review")
    if not check_source_geometry((HERE / "native-map-plan/crest-road.xodr").read_text(), site):
        raise ValueError("OpenDRIVE source geometry differs")
    turn_x = 0 if placement == "near_summit" else -40
    if (site["turn_site_xyz_m"][0] != turn_x or
            site["occluder"]["target_direction"] != direction or
            build["placement"] != placement or build["occluded_direction"] != direction):
        raise ValueError("Declared crest placement or obscured direction differs")
    center_x = site["occluder"]["center_xyz_m"][0]
    half_x = site["occluder"]["half_extent_xyz_m"][0]
    if not math.isclose(abs(center_x - turn_x) - half_x, PROBES[probe][1], abs_tol=1e-7):
        raise ValueError("Planned prop near face differs from probe ray station")
    context = read(attempt / "curve_context.json")
    if (context.get("site_source_sha256") != config["site_source"]["sha256"] or
            context.get("incoming_lanes") != site["incoming_lanes"] or
            context.get("turn_site_xyz_m") != site["turn_site_xyz_m"]):
        raise ValueError("Original context/site binding differs")
    mapping = rows(attempt / "video_frames.jsonl")
    motion = rows(attempt / "motion_history.jsonl")
    trace = rows(attempt / "trace.jsonl")
    evidence = rows(attempt / "capture/evidence.jsonl")
    turns = rows(attempt / "turn_history.jsonl")
    if any(len(collection) != 1100 for collection in (mapping, motion, trace, evidence, turns)):
        raise ValueError("Crest branch source duration differs")
    excluded = {"site_source", "selected_case_id", "supported_case_ids"} if canonical else {"site_source"}
    fixed_config = {k: v for k, v in config.items() if k not in excluded}
    fixed_site = {k: v for k, v in site.items() if k not in
                  ("turn_site_xyz_m", "incoming_lanes", "u_turn_route_xyz_m", "camera_poses", "occluder")}
    lane_ids = {lane["lane_id"] for lane in site["incoming_lanes"].values()}
    blocked_lane = site["incoming_lanes"][direction]["lane_id"]
    normalized = []
    worlds = []
    for index, (frame, actors, tick, ray, turn) in enumerate(zip(mapping, motion, trace, evidence, turns)):
        native, time = frame.get("native_frame"), frame.get("time_s")
        if (frame.get("video_frame") != index or actors.get("video_frame") != index or
                actors.get("native_frame") != native or tick.get("frame") != native or
                ray.get("original_frame") != native or turn.get("frame") != native or
                actors.get("site_source_sha256") != config["site_source"]["sha256"] or
                any(not math.isclose(t, time, abs_tol=.001) for t in
                    (tick.get("time_s"), ray.get("recording_time_s"), turn.get("time_s"))) or
                not math.isclose(time - mapping[0]["time_s"], index / 20, abs_tol=.005)):
            raise ValueError("Crest branch original frame/time join differs")
        if set(actors.get("approaches", {})) != {"approach_a", "approach_b"}:
            raise ValueError("Both approaching directions required")
        for label, actor in actors["approaches"].items():
            lane = site["incoming_lanes"][label]
            if actor.get("road_lane") != [lane["road_id"], lane["lane_id"]]:
                raise ValueError("Approaching actor lane differs")
        vis = ray.get("visibility", {})
        if vis.get("probe_distance_m") != 152.4 or set(vis.get("required_lane_ids", [])) != lane_ids:
            raise ValueError("Crest branch source ray inventory differs")
        rays = {row.get("lane_id"): row for row in vis.get("approaches", [])}
        if set(rays) != lane_ids:
            raise ValueError("Both original approach rays required")
        blocked = rays[blocked_lane]
        clear = rays[next(iter(lane_ids - {blocked_lane}))]
        horizon = blocked.get("any_body_sight_horizon", {})
        bracket = horizon.get("bracket_m")
        if (horizon.get("bound") != "first_sampled_occlusion" or bracket != PROBES[probe][2] or
                blocked.get("any_sample_clear_at_probe") is not PROBES[probe][3] or
                clear.get("any_body_sight_horizon", {}).get("bound") != "at_least" or
                clear.get("any_sample_clear_at_probe") is not True):
            raise ValueError("Direction-specific short-of-500ft sight source differs")
        normalized.append({"ego": normalized_actor(actors["ego"], turn_x),
                           "approach_a": normalized_actor(actors["approaches"]["approach_a"], turn_x),
                           "approach_b": normalized_actor(actors["approaches"]["approach_b"], turn_x)})
        worlds.append(ray.get("world"))
    return {"name": name, "case_id": case, "placement": placement, "direction": direction,
            "fixed_config": fixed_config, "fixed_site": fixed_site,
            "normalized_motion": normalized, "worlds": worlds,
            "source_sha256": {source: hashes[source] for source in required},
            "physical_acceptance_claimed": False}


def audit(attempts, probe="short_of_500ft"):
    names = names_for(probe)
    if set(attempts) != set(names):
        raise ValueError("Four declared crest branch attempts required")
    views = {name: inspect(name, attempts[name], probe) for name in names}
    first = views[names[0]]
    for name, view in views.items():
        for key in ("fixed_config", "fixed_site", "normalized_motion", "worlds"):
            if view[key] != first[key]:
                raise ValueError("Unrelated fixed source condition differs: " + key + " in " + name)
    return {"format": "worker-crest-branch-comparison-diagnostic",
            "case_id": HERE.name + "__crest__" + probe, "alternatives": list(names),
            "source_sha256": {name: views[name]["source_sha256"] for name in names},
            "software_checks_passed": True, "passed": False,
            "physical_acceptance_claimed": False,
            "limitations": ["Synthetic rays and roads do not prove physical occlusion or driver recognition"]}


def audit_canonical_pairs(attempts):
    names = ("canonical-at-approach-b", "canonical-at-near-b", "canonical-at-approach-a", "canonical-at-near-a")
    if set(attempts) != set(names):
        raise ValueError("Four distinct exact 500-foot crest attempts required")
    views = {name: inspect(name, attempts[name], "at_500ft", canonical=True) for name in names}
    pairs = ((names[0], names[1], "site_placement"), (names[0], names[2], "occluded_direction"),
             (names[2], names[3], "site_placement"), (names[1], names[3], "occluded_direction"))
    for left, right, variable in pairs:
        a, b = views[left], views[right]
        fixed_variable = "direction" if variable == "site_placement" else "placement"
        if a[variable.replace("site_placement", "placement").replace("occluded_direction", "direction")] == b[variable.replace("site_placement", "placement").replace("occluded_direction", "direction")]:
            raise ValueError("Declared comparison variable did not change")
        if a[fixed_variable] != b[fixed_variable]:
            raise ValueError("Controlled comparison changed second site variable")
        for key in ("fixed_config", "fixed_site", "normalized_motion", "worlds"):
            if a[key] != b[key]:
                raise ValueError("Unrelated fixed source condition differs: " + key)
    return {"format": "worker-crest-exact-comparison-diagnostic",
            "comparisons": [
                {"case_ids": [views[left]["case_id"], views[right]["case_id"]], "deliberate_difference": variable}
                for left, right, variable in pairs],
            "source_sha256": {name: views[name]["source_sha256"] for name in names},
            "software_checks_passed": True, "passed": False,
            "physical_acceptance_claimed": False,
            "limitations": ["Synthetic rays and roads do not prove physical occlusion or driver recognition"]}


def audit_canonical_short_pair(attempts):
    names = ("canonical-short-approach-b", "canonical-short-near-b",
             "canonical-short-approach-a", "canonical-short-near-a")
    if set(attempts) != set(names):
        raise ValueError("Four distinct exact short-of-500-foot crest attempts required")
    views = {name: inspect(name, attempts[name], "short_of_500ft", canonical=True) for name in names}
    pairs = ((names[0], names[1], "site_placement"), (names[0], names[2], "occluded_direction"),
             (names[2], names[3], "site_placement"), (names[1], names[3], "occluded_direction"))
    for left, right, variable in pairs:
        a, b = views[left], views[right]
        changing = "placement" if variable == "site_placement" else "direction"
        fixed = "direction" if variable == "site_placement" else "placement"
        if a[changing] == b[changing] or a[fixed] != b[fixed]:
            raise ValueError("Short comparison changed wrong site variable")
        for key in ("fixed_config", "fixed_site", "normalized_motion", "worlds"):
            if a[key] != b[key]:
                raise ValueError("Unrelated short comparison source condition differs: " + key)
    return {"format": "worker-crest-exact-short-comparison-diagnostic",
            "comparisons": [{"case_ids": [views[left]["case_id"], views[right]["case_id"]],
                             "deliberate_difference": variable} for left, right, variable in pairs],
            "source_sha256": {name: views[name]["source_sha256"] for name in names},
            "software_checks_passed": True, "passed": False, "physical_acceptance_claimed": False,
            "limitations": ["Synthetic rays and roads do not prove physical occlusion or driver recognition"]}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    for name in NAMES:
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    print(json.dumps(audit({name: getattr(args, name.replace("-", "_")) for name in NAMES}), sort_keys=True))
