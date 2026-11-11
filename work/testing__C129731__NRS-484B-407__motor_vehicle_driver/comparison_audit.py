"""Independent three-probe curve/crest source comparison; no legal verdict."""
import argparse
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
BOUNDARY_M = 152.4
PROBES = ("short_of_500ft", "at_500ft", "beyond_500ft")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing original comparison source: " + str(path))
    return json.loads(path.read_text())


def rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing original comparison source: " + str(path))
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def view(attempt, case_id, probe, diagnostic):
    attempt = Path(attempt).resolve()
    config = read(attempt / "config.json")
    if config.get("selected_case_id") != case_id:
        raise ValueError("Comparison attempt selected another case")
    if (config.get("rate_hz"), config.get("duration_s"), len(config.get("cameras", []))) != (20, 55, 4):
        raise ValueError("Comparison capture contract changed")
    site_path = attempt / config["site_source"]["path"]
    if sha(site_path) != config["site_source"]["sha256"]:
        raise ValueError("Comparison site source changed")
    site = read(site_path)
    if site.get("probe") != probe:
        raise ValueError("Comparison probe differs from exact case")
    result = read(attempt / "result.json")
    if result.get("case_id") != case_id or result.get("physical_acceptance_claimed") is not False:
        raise ValueError("Comparison result identity or acceptance claim differs")
    if diagnostic:
        if result.get("provenance_kind") != "synthetic_fixture":
            raise ValueError("Diagnostic comparison requires synthetic provenance")
    elif result.get("provenance_kind") != "native":
        raise ValueError("Native source required for physical comparison")
    source_hashes = result.get("source_evidence_hashes", {})
    for name in ("config.json", config["site_source"]["path"], "motion_history.jsonl",
                 "video_frames.jsonl", "trace.jsonl", "capture/evidence.jsonl",
                 "turn_history.jsonl", "curve_context.json"):
        if source_hashes.get(name) != sha(attempt / name):
            raise ValueError("Original comparison source hash changed: " + name)
    mapping = rows(attempt / "video_frames.jsonl")
    motion = rows(attempt / "motion_history.jsonl")
    trace = rows(attempt / "trace.jsonl")
    rays = rows(attempt / "capture/evidence.jsonl")
    turns = rows(attempt / "turn_history.jsonl")
    if not all(len(x) == 1100 for x in (mapping, motion, trace, rays, turns)):
        raise ValueError("Comparison source duration differs")
    lane_ids = {lane["lane_id"] for lane in site["incoming_lanes"].values()}
    horizons = []
    first_time = mapping[0]["time_s"]
    for index, (frame, pose, tick, ray, turn) in enumerate(zip(mapping, motion, trace, rays, turns)):
        native, time = frame.get("native_frame"), frame.get("time_s")
        if (frame.get("video_frame") != index or pose.get("video_frame") != index or
                pose.get("native_frame") != native or tick.get("frame") != native or
                ray.get("original_frame") != native or turn.get("frame") != native or
                pose.get("site_source_sha256") != config["site_source"]["sha256"] or
                any(abs(other-time) > 1e-3 for other in
                    (tick.get("time_s"), ray.get("recording_time_s"), turn.get("time_s"))) or
                not math.isclose(time-first_time, index/20, abs_tol=.005)):
            raise ValueError("Original comparison frame/time join differs")
        if set(pose.get("approaches", {})) != {"approach_a", "approach_b"}:
            raise ValueError("Both original approaching vehicles required")
        for direction, actor in pose["approaches"].items():
            lane = site["incoming_lanes"][direction]
            if actor.get("road_lane") != [lane["road_id"], lane["lane_id"]]:
                raise ValueError("Original approach lane changed")
        visibility = ray.get("visibility", {})
        if visibility.get("probe_distance_m") != BOUNDARY_M or set(visibility.get("required_lane_ids", [])) != lane_ids:
            raise ValueError("Original two-direction probe missing")
        approaches = {row.get("lane_id"): row for row in visibility.get("approaches", [])}
        if set(approaches) != lane_ids:
            raise ValueError("Original two-direction rays missing")
        first = approaches[site["incoming_lanes"]["approach_a"]["lane_id"]]
        second = approaches[site["incoming_lanes"]["approach_b"]["lane_id"]]
        horizon = first.get("any_body_sight_horizon", {})
        bracket = horizon.get("bracket_m")
        if (horizon.get("bound") != "first_sampled_occlusion" or
                not isinstance(bracket, list) or len(bracket) != 2 or
                any(type(v) not in (int, float) or not math.isfinite(v) for v in bracket) or
                bracket[0] > bracket[1] or
                second.get("any_sample_clear_at_probe") is not True):
            raise ValueError("Original comparison sight bracket invalid")
        center = (bracket[0]+bracket[1])/2
        if ((probe == "short_of_500ft" and not (center < BOUNDARY_M and first.get("any_sample_clear_at_probe") is False)) or
                (probe == "at_500ft" and not (abs(center-BOUNDARY_M) <= .25 and first.get("any_sample_clear_at_probe") is True)) or
                (probe == "beyond_500ft" and not (center > BOUNDARY_M and first.get("any_sample_clear_at_probe") is True))):
            raise ValueError("Original sight bracket differs from declared probe")
        horizons.append(center)
    config_fixed = {k: v for k, v in config.items() if k not in ("selected_case_id", "site_source")}
    site_fixed = {k: v for k, v in site.items() if k not in ("probe", "occluder")}
    return {"case_id": case_id, "probe": probe, "attempt": str(attempt),
            "config_fixed": config_fixed, "site_fixed": site_fixed,
            "first_motion": motion[0]["ego"], "first_approaches": motion[0]["approaches"],
            "first_world": rays[0].get("world"), "horizons": horizons,
            "source_sha256": {name: sha(attempt / name) for name in
                ("motion_history.jsonl", "video_frames.jsonl", "capture/evidence.jsonl", "turn_history.jsonl")}}


def audit_group(comparison_id, attempts, *, diagnostic=False, folder=HERE):
    plan = read(Path(folder) / "case-plan.json")
    matching = [row for row in plan["comparisons"] if row["comparison_id"] == comparison_id]
    if len(matching) != 1 or len(matching[0]["case_ids"]) != 3 or len(attempts) != 3:
        raise ValueError("Exact three-case comparison required")
    group = matching[0]
    views = [view(path, case, probe, diagnostic) for path, case, probe in
             zip(attempts, group["case_ids"], PROBES)]
    for other in views[1:]:
        for key in ("config_fixed", "site_fixed", "first_motion", "first_approaches"):
            if other[key] != views[0][key]:
                raise ValueError("Fixed comparison condition differs: " + key)
        if other["first_world"] != views[0]["first_world"]:
            raise ValueError("Fixed weather, traffic or device source context differs")
    if not diagnostic and not views[0]["first_world"]:
        raise ValueError("Native comparison needs retained weather, traffic and device context")
    return {"format": "worker-comparison-audit-diagnostic" if diagnostic else "worker-comparison-audit",
            "comparison_id": comparison_id, "case_ids": group["case_ids"],
            "passed": not diagnostic, "software_checks_passed": True,
            "physical_acceptance_claimed": False,
            "fixed_conditions_checked": ["config", "site except engineered occluder",
                "initial ego and both approaches", "first source world context", "1100-frame time join"],
            "source_horizon_m": {row["probe"]: row["horizons"][0] for row in views},
            "source_sha256": {row["case_id"]: row["source_sha256"] for row in views}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True,
                        choices=("curve_visibility_boundary", "crest_visibility_boundary"))
    parser.add_argument("--attempts", nargs=3, type=Path, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit_group(args.comparison, args.attempts,
                                 diagnostic=args.diagnostic), sort_keys=True))
