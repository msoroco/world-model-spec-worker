"""Independent fixed-condition audit for the two C104496 controlled comparisons."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
PAIRS = {"planned_comparison": ("probe_01", "probe_02"),
         "curvature_comparison": ("probe_01", "probe_03")}
FIXED = ("assignment_id", "law_id", "cell_id", "actor", "camera_policy",
         "requested_speed_mps", "rate_hz", "duration_s", "frames", "ego_blueprint",
         "other_vehicle_blueprint")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def config_from_construction(probe):
    construction = load(HERE / "selected" / probe / "primary" / "construction.json")
    return json.loads(next(row["content"] for row in construction["files"] if row["path"] == "config.json"))


def check(compare, a, b):
    if compare not in PAIRS:
        raise ValueError("Unknown exact comparison")
    for key in FIXED:
        if a.get(key) != b.get(key):
            raise ValueError("Fixed condition changed: " + key)
    if a.get("candidate_id") != "primary" or b.get("candidate_id") != "primary":
        raise ValueError("Compare matching primary candidates")
    if a.get("original_native_observed") is True or b.get("original_native_observed") is True:
        raise ValueError("Authored config cannot attest original Native observation")
    if compare == "planned_comparison":
        if a.get("grade_height_m") != 0.8 or b.get("grade_height_m") != 12.0 or a.get("crest_station_m") != b.get("crest_station_m") or a.get("curve_radius_m") != b.get("curve_radius_m"):
            raise ValueError("Crest grade comparison changed more than declared")
        changed = "quadratic grade height: 0.8 m versus 12 m"
    else:
        if a.get("grade_height_m") != b.get("grade_height_m") or a.get("grade_height_m") != 0.8 or a.get("curve_radius_m") is not None or b.get("curve_radius_m") != 300.0:
            raise ValueError("Curve comparison changed more than declared")
        changed = "straight versus 300 m radius curve at 0.8 m grade"
    if a.get("road_sha256") == b.get("road_sha256"):
        raise ValueError("Declared road geometry difference absent")
    return {"fixed_conditions": list(FIXED), "declared_difference": changed}


def audit(compare, attempt_a, attempt_b, output):
    probes = PAIRS.get(compare)
    if probes is None:
        raise ValueError("Unknown exact comparison")
    sources = []
    configs = []
    for attempt, probe in zip((attempt_a, attempt_b), probes):
        root = Path(attempt).resolve()
        cfg_path, result_path = root / "config.json", root / "result.json"
        if not cfg_path.is_file() or not result_path.is_file():
            raise ValueError("Missing original comparison source")
        cfg, result = load(cfg_path), load(result_path)
        if cfg.get("case_id") != AID + "__" + probe or result.get("case_id") != cfg["case_id"]:
            raise ValueError("Comparison case identity changed")
        if result.get("provenance_kind") != "original_native" or result.get("diagnostic_fixture") is True:
            raise ValueError("Missing original comparison source")
        if result.get("physical_checks", {}).get("maneuver", {}).get("status") != "met" or not result.get("maneuver_completed"):
            raise ValueError("Comparison lacks observed completed reversal")
        for row in result.get("recording_evidence", []):
            path = (root / row["reference"]).resolve()
            if root not in path.parents or not path.is_file():
                raise ValueError("Missing original comparison channel")
        configs.append(cfg)
        sources.append({"case_id": cfg["case_id"], "config_sha256": sha(cfg_path), "result_sha256": sha(result_path), "measured_values": result.get("measured_values")})
    isolation = check(compare, *configs)
    if not all(source["measured_values"] for source in sources):
        raise ValueError("Comparison lacks source measured values")
    payload = {"format": "worker-comparison-audit", "passed": True,
               "comparison_id": AID + "__" + compare, "cases": sources,
               "isolation": isolation, "original_source_verified": True,
               "legal_judgment_pending": True}
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def selftest(compare, negative):
    a, b = (config_from_construction(probe) for probe in PAIRS[compare])
    if negative:
        b["camera_policy"] = "changed_view"
        check(compare, a, b)
        raise AssertionError("changed fixed condition accepted")
    evidence = check(compare, a, b)
    return {"comparison": compare, "isolated": evidence,
            "scope": "authored CPU construction only; original comparison pending"}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--comparison", required=True, choices=PAIRS)
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--negative", action="store_true")
    p.add_argument("--attempt-a")
    p.add_argument("--attempt-b")
    p.add_argument("--output")
    args = p.parse_args()
    print(json.dumps(selftest(args.comparison, args.negative) if args.self_test else audit(args.comparison, args.attempt_a, args.attempt_b, args.output), indent=2))
