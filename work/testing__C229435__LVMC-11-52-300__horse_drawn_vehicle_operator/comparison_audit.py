"""Independent source-bound audit of nighttime parking comparison isolation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _read(path):
    return json.loads(Path(path).read_text())


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(plan, comparison_id, attempts):
    plan = Path(plan)
    data = _read(plan)
    selected = next((item for item in data["comparisons"] if item["comparison_id"] == comparison_id), None)
    _require(selected is not None, "unknown exact comparison")
    _require(len(attempts) == 2, "comparison needs two original attempts")
    values = []
    result_hashes = {}
    for case_id, attempt in zip(selected["case_ids"], attempts):
        attempt = Path(attempt)
        path = attempt / "result.json"
        _require(path.is_file(), "missing saved exact result: " + case_id)
        result = _read(path)
        _require(result.get("case_id") == case_id, "wrong exact comparison case")
        _require(result.get("physical_acceptance_claimed") is False, "comparison cannot adopt an acceptance claim")
        measured = result.get("measured_values", {})
        for key in ("source_hashes", "subject_body_start_xy_m", "other_vehicle_body_start_xy_m", "elapsed_s", "night_overlap_s", "start_local", "end_local", "self_propelled", "activity"):
            _require(key in measured, "missing original comparison measurement: " + key)
        for name, checksum in measured["source_hashes"].items():
            _require(type(checksum) is str and len(checksum) == 64, "unbound original source hash: " + name)
        source_manifest = attempt / "night-parking-sources.json"
        _require(source_manifest.is_file(), "missing original source manifest")
        sources = _read(source_manifest)
        _require(sources.get("format") == "night-parking-original-sources-v1" and
                 set(sources.get("sources", {})) == set(measured["source_hashes"]),
                 "original source inventory differs from saved measurement")
        for name, descriptor in sources["sources"].items():
            relative = Path(descriptor["path"])
            _require(not relative.is_absolute() and ".." not in relative.parts, "original source path escapes attempt")
            original = attempt / relative
            _require(original.is_file() and _sha(original) == descriptor["sha256"] == measured["source_hashes"][name],
                     "stale original comparison source: " + name)
        values.append(measured)
        result_hashes[case_id] = _sha(path)
    left, right = values
    _require(left["source_hashes"].get("context") == right["source_hashes"].get("context"), "qualifying street/timezone context changed")
    _require(left["subject_body_start_xy_m"] == right["subject_body_start_xy_m"] and
             left["other_vehicle_body_start_xy_m"] == right["other_vehicle_body_start_xy_m"],
             "physical vehicle placement changed")
    if comparison_id != "nonmotor_exception":
        _require(left["source_hashes"].get("classification") == right["source_hashes"].get("classification"), "vehicle classification changed outside exception comparison")
    if comparison_id != "parking_vs_loading":
        _require(left["source_hashes"].get("activity") == right["source_hashes"].get("activity"), "parking activity source changed outside activity comparison")
    if comparison_id.startswith("duration_"):
        _require(left["start_local"] == right["start_local"], "duration comparison changed start civil time")
        _require(left["elapsed_s"] != right["elapsed_s"], "duration comparison did not vary measured duration")
    elif comparison_id == "night_vs_day":
        _require(left["elapsed_s"] == right["elapsed_s"], "clock comparison changed parked duration")
        _require(left["night_overlap_s"] != right["night_overlap_s"], "clock comparison did not vary measured nighttime overlap")
    elif comparison_id.startswith("one_am_"):
        pair = (left["start_local"][11:19], right["start_local"][11:19])
        expected = ("00:59:59", "01:00:00") if comparison_id == "one_am_below_at" else ("01:00:00", "01:00:01")
        _require(left["elapsed_s"] == right["elapsed_s"] and pair == expected,
                 "01:00 endpoint comparison changed parked duration or exact endpoint probes")
    elif comparison_id.startswith("six_am_"):
        pair = (left["end_local"][11:19], right["end_local"][11:19])
        expected = ("05:59:59", "06:00:00") if comparison_id == "six_am_below_at" else ("06:00:00", "06:00:01")
        _require(left["elapsed_s"] == right["elapsed_s"] and pair == expected,
                 "06:00 endpoint comparison changed parked duration or exact endpoint probes")
    elif comparison_id == "nonmotor_exception":
        _require(left["elapsed_s"] == right["elapsed_s"] and left["start_local"] == right["start_local"], "vehicle exception comparison changed episode timing")
        _require(left["self_propelled"] != right["self_propelled"], "vehicle exception comparison did not vary motive power")
    elif comparison_id == "parking_vs_loading":
        _require(left["elapsed_s"] == right["elapsed_s"] and left["start_local"] == right["start_local"], "activity comparison changed episode timing")
        _require(left["activity"] != right["activity"], "activity comparison did not vary actual activity")
    return {"format": "worker-comparison-audit", "comparison_id": comparison_id,
            "case_ids": selected["case_ids"], "result_sha256": result_hashes,
            "fixed_conditions_checked": selected["fixed_conditions"],
            "deliberate_differences_checked": selected["deliberate_differences"],
            "passed": True, "legal_verdict_claimed": False, "physical_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--left", required=True)
    parser.add_argument("--right", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    receipt = audit(args.plan, args.comparison, [args.left, args.right])
    Path(args.output).write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
