"""Independent source-bound audit of the three sidewalk bypass comparisons."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = json.loads((HERE / "case-plan.json").read_text())
PAIRS = {row["comparison_id"]: row for row in PLAN["comparisons"]}
FIXED = ("actor", "cell_id", "law_id", "duration_s", "rate_hz", "cameras",
         "required_atoms", "source_packets", "recording_description",
         "lateral_shift_m", "obstruction_raise_z_m", "candidate_id")
SOURCES = ("pedestrian-original.jsonl", "video_frames.jsonl",
           "camera-sources.jsonl", "sidewalk_context.json")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def config_from_construction(case_id):
    suffix = case_id.rsplit("__", 1)[-1]
    construction = read(HERE / "native" / "selected-drafts" / suffix /
                        "primary" / "construction.json")
    return json.loads(next(row["content"] for row in construction["files"]
                           if row["path"] == "config.json"))


def isolate(comparison_id, first, second):
    comparison = PAIRS.get(comparison_id)
    if comparison is None:
        raise ValueError("Unknown exact comparison")
    if [first.get("case_id"), second.get("case_id")] != comparison["case_ids"]:
        raise ValueError("Comparison case identity changed")
    for key in FIXED:
        if first.get(key) != second.get(key):
            raise ValueError("Fixed condition changed: " + key)
    variable = comparison["deliberate_differences"]
    if len(variable) != 1:
        raise ValueError("Comparison variable is ambiguous")
    suffixes = [case.rsplit("__", 1)[-1] for case in comparison["case_ids"]]
    expected = {"pedestrian_bypass_path": ["condition_a", "condition_b"],
                "sidewalk_travel_direction": ["direction_east", "direction_west"],
                "intervening_area_passability": ["bike_passable", "bike_impassable"]}
    if suffixes != expected.get(variable[0]) or [first.get("case_suffix"),
                                                  second.get("case_suffix")] != suffixes:
        raise ValueError("Declared comparison difference missing")
    if (variable[0] == "sidewalk_travel_direction" and
            ["west" if suffix == "direction_west" else "east" for suffix in suffixes]
            != ["east", "west"]):
        raise ValueError("Direction pair changed")
    if variable[0] == "intervening_area_passability" and suffixes != [
            "bike_passable", "bike_impassable"]:
        raise ValueError("Intervening-area pair changed")
    return {"fixed_fields": list(FIXED), "declared_difference": variable[0]}


def audit(comparison_id, attempt_a, attempt_b, output):
    roots = [Path(attempt_a).resolve(), Path(attempt_b).resolve()]
    configs = []
    cases = []
    for root in roots:
        config_path, result_path = root / "config.json", root / "result.json"
        if not config_path.is_file() or not result_path.is_file():
            raise ValueError("Missing original comparison source")
        config, result = read(config_path), read(result_path)
        if result.get("case_id") != config.get("case_id") or result.get(
                "provenance_kind") != "original_native" or result.get(
                "diagnostic_fixture") is True:
            raise ValueError("Missing original Native comparison result")
        measured = result.get("measured_values", {})
        if (measured.get("source_kind") != "original_native_measurement" or
                measured.get("frames") != 600 or
                measured.get("first_full_sidewalk_return_frame") is None):
            raise ValueError("Missing source-measured bypass and return")
        hashes = {}
        for name in SOURCES:
            source = root / name
            if not source.is_file():
                raise ValueError("Missing original comparison source: " + name)
            hashes[name] = sha(source)
        configs.append(config)
        cases.append({"case_id": config["case_id"],
                      "config_sha256": sha(config_path),
                      "result_sha256": sha(result_path),
                      "original_source_hashes": hashes,
                      "measured_values": measured})
    isolation = isolate(comparison_id, *configs)
    first, second = (case["measured_values"] for case in cases)
    variable = isolation["declared_difference"]
    if variable == "pedestrian_bypass_path":
        values = [item.get("nearest_road_edge_center_distance_m")
                  for item in (first, second)]
        if any(type(value) not in (int, float) for value in values) or values[0] == values[1]:
            raise ValueError("Bypass path difference lacks original edge measurement")
    elif variable == "sidewalk_travel_direction":
        if [first.get("walking_direction_observed"),
                second.get("walking_direction_observed")] != ["east", "west"]:
            raise ValueError("Direction difference lacks original motion")
    elif variable == "intervening_area_passability":
        if ([first.get("intervening_area_requested_impassable"),
             second.get("intervening_area_requested_impassable")] != [False, True] or
                any(item.get("bike_lane_designation") != "native_biking_lane"
                    for item in (first, second))):
            raise ValueError("Bicycle-lane condition lacks original map and request")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {"format": "worker-comparison-audit", "passed": True,
               "comparison_id": comparison_id, "cases": cases,
               "isolation": isolation, "legal_judgment_pending": True,
               "physical_review_pending": True}
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def selftest(comparison_id, negative):
    comparison = PAIRS[comparison_id]
    first, second = [config_from_construction(case) for case in comparison["case_ids"]]
    if negative:
        second["duration_s"] = 29
        isolate(comparison_id, first, second)
        raise AssertionError("Changed duration accepted")
    return isolate(comparison_id, first, second)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True, choices=PAIRS)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--negative", action="store_true")
    parser.add_argument("--attempt-a")
    parser.add_argument("--attempt-b")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = (selftest(args.comparison, args.negative) if args.self_test else
              audit(args.comparison, args.attempt_a, args.attempt_b, args.output))
    print(json.dumps(result, indent=2))
