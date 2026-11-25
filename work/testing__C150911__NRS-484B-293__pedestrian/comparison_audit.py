"""Independent saved-original audit of one declared NRS 484B.293 comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import copy
from pathlib import Path

from crosswalk_delivery import audit_pair, measure
from independent_cpu_delivery import audit as audit_delivery

ROOT = Path(__file__).resolve().parent
REQUIRED = ("original-site.json", "original-pedestrian.jsonl",
            "original-obstacles.jsonl", "original-participants.jsonl",
            "original-receipt.json", "video_frames.jsonl", "trace.jsonl",
            "config.json", "result.json")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read(path):
    return json.loads(Path(path).read_text())


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def _required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError("Missing required original source: " + name)
    return path


def _saved(attempt, expected_case, diagnostic):
    attempt = Path(attempt).resolve()
    files = {name: _required(attempt, name) for name in REQUIRED}
    config = _read(files["config.json"])
    if config.get("selected_case_id") != expected_case or config.get("law_id") != "NRS-484B-293" or (
            config.get("cell_id"), config.get("actor")) != ("C150911", "pedestrian"):
        raise ValueError("saved comparison case/law/cell/actor identity differs")
    if config.get("duration_s") != 45 or config.get("rate_hz") != 20 or len(config.get("cameras", [])) != 4:
        raise ValueError("saved comparison duration or camera contract differs")
    receipt = _read(files["original-receipt.json"])
    if receipt.get("case_id") != expected_case or receipt.get("diagnostic_fixture") is not diagnostic:
        raise ValueError("original receipt case or provenance differs")
    if not diagnostic and receipt.get("frame_count") != 900:
        raise ValueError("original 900-frame passage required")
    if not diagnostic:
        seal = _read(_required(attempt, "capture-seal.json"))
        if seal.get("provenance_kind") != "native" or seal.get("diagnostic_fixture") is not False or (
                seal.get("frames") != 900 or seal.get("events") != [
                "capture_finished", "encoders_closed", "restoration_verified"]):
            raise ValueError("sealed original Native closure differs")
        for name in ("original-site.json", "original-pedestrian.jsonl",
                     "original-obstacles.jsonl", "original-participants.jsonl",
                     "video_frames.jsonl", "trace.jsonl", "overview.mkv",
                     "approach.mkv", "reference_corner.mkv", "driver_reference.mkv"):
            if seal.get("sources", {}).get(name) != _sha(_required(attempt, name)):
                raise ValueError("sealed original Native source changed: " + name)
    media = audit_delivery(attempt, expected_case, diagnostic=diagnostic)
    site = _read(files["original-site.json"])
    walker, obstacles, participants = [_rows(files[name]) for name in REQUIRED[1:4]]
    motion = measure(site, walker, obstacles, participants)
    mapping = _rows(files["video_frames.jsonl"])
    trace = _rows(files["trace.jsonl"])
    if len(trace) != len(mapping) or len(walker) != len(trace):
        raise ValueError("original trace/frame map length differs")
    for pedestrian, mapped, original in zip(walker, mapping, trace):
        if original.get("frame") != pedestrian["frame"] or original.get("frame") != mapped.get("carla_frame") or (
                abs(original.get("time_s", -1) - mapped.get("time_s", -2)) > 1e-4):
            raise ValueError("original trace/frame identity join differs")
    if motion["legal_practicability"] != "unresolved":
        raise ValueError("unsupported practicability verdict")
    return {"attempt": str(attempt), "config": config, "site": site,
            "motion": motion, "media": media,
            "source_sha256": {name: _sha(path) for name, path in files.items()},
            "video_sha256": media["full_video_decode"]}


def compare(comparison_id, first_attempt, second_attempt, diagnostic=False):
    plan = _read(ROOT / "case-plan.json")
    declared = next((row for row in plan["comparisons"] if row["comparison_id"] == comparison_id), None)
    if declared is None or len(declared.get("case_ids", [])) != 2:
        raise ValueError("unknown exact comparison")
    first = _saved(first_attempt, declared["case_ids"][0], diagnostic)
    second = _saved(second_attempt, declared["case_ids"][1], diagnostic)
    normalized = []
    for item in (first, second):
        config = copy.deepcopy(item["config"])
        config.pop("selected_case_id", None)
        config.get("case", {}).pop("case_id", None)
        normalized.append(config)
    if normalized[0] != normalized[1]:
        raise ValueError("fixed comparison config fields differ")
    differences = set(declared["deliberate_differences"])
    permitted = {"obstacle_source_sha256"} if "obstacle_source_sha256" in differences else set()
    pair = audit_pair(first["motion"], second["motion"], permitted)
    if first["source_sha256"]["original-pedestrian.jsonl"] == second["source_sha256"]["original-pedestrian.jsonl"]:
        raise ValueError("comparison reused one original pedestrian trace")
    for key in ("crosswalk_width_m", "crosswalk_id", "one_way_road_id", "governing_signal",
                "pedestrian_access", "crosswalk_qualification"):
        if first["site"].get(key) != second["site"].get(key):
            raise ValueError("fixed crosswalk context differs: " + key)
    if "entry_exit_order" in differences:
        if (first["site"]["entry_center"] != second["site"]["exit_center"] or
                first["site"]["exit_center"] != second["site"]["entry_center"]):
            raise ValueError("declared opposite passage direction not realized")
    elif (first["site"]["entry_center"] != second["site"]["entry_center"] or
          first["site"]["exit_center"] != second["site"]["exit_center"]):
        raise ValueError("fixed passage direction differs")
    lateral = [sum(row["right_lateral_m"] for row in item["motion"]["full_original_trace"])
               for item in (first, second)]
    if comparison_id in ("forward_half", "reverse_half") and not (lateral[0] > 0 > lateral[1]):
        raise ValueError("declared direction-relative half contrast absent")
    if comparison_id == "directional_right" and not all(value > 0 for value in lateral):
        raise ValueError("opposite directions did not retain relative right half")
    if comparison_id == "right_half_obstruction":
        if not all(value > 0 for value in lateral):
            raise ValueError("obstruction comparison did not retain relative right half")
        if first["motion"]["fixed_sources"]["obstacle_source_sha256"] == (
                second["motion"]["fixed_sources"]["obstacle_source_sha256"]):
            raise ValueError("declared obstruction source did not change")
        clear = [row["available_right_width_m"] for row in first["motion"]["full_original_trace"]]
        blocked = [row["available_right_width_m"] for row in second["motion"]["full_original_trace"]]
        if not min(blocked) < min(clear):
            raise ValueError("declared right-half obstruction did not reduce observed space")
    if not all(math.isfinite(value) for value in lateral):
        raise ValueError("nonfinite original lateral observations")
    return {"format": "worker-comparison-audit", "comparison_id": comparison_id,
        "case_ids": declared["case_ids"], "passed": True,
        "diagnostic_only": diagnostic, "physical_acceptance": False,
        "legal_practicability": "unresolved", "fixed_conditions": declared["fixed_conditions"],
        "deliberate_differences": declared["deliberate_differences"],
        "fixed_source_checks": pair["fixed_sources_checked"],
        "original_frame_counts": pair["compared_original_frames"],
        "direction_relative_lateral_sums_m": lateral,
        "attempts": [{"path": item["attempt"], "source_sha256": item["source_sha256"],
                      "video_sha256": item["video_sha256"]} for item in (first, second)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--first-attempt", type=Path, required=True)
    parser.add_argument("--second-attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    args = parser.parse_args()
    for source in (args.first_attempt, args.second_attempt):
        if args.output.resolve() == source.resolve() or source.resolve() in args.output.resolve().parents:
            raise ValueError("comparison report must be outside original attempts")
    result = compare(args.comparison, args.first_attempt, args.second_attempt,
                     diagnostic=args.diagnostic_fixture)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise ValueError("retain previous comparison report")
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"comparison_id": args.comparison, "passed": True,
                      "diagnostic_only": args.diagnostic_fixture}))


if __name__ == "__main__":
    main()
