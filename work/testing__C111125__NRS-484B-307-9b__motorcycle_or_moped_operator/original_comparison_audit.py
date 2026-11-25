"""Independently audit two local original saved attempts for one exact comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from audit_delivery_prepared import join_original_frames, rows
from comparison_audit import PAIRS, audit_pair
from delivery_audit import audit_saved
from media_decode import audit_four_views
from prove_comparison import summary

HERE = Path(__file__).resolve().parent
PROFILE = {"overview": (1920, 1080), "approach": (1280, 720),
           "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def attempt(root, expected_case, diagnostic=False):
    root = Path(root).resolve()
    saved = read(root / "saved-manifest.json")
    site = read(root / "native-site.json")
    provenance = read(root / "acquisition-provenance.json")
    if saved.get("case_id") != expected_case or saved.get("assignment_id") != HERE.name or (
            site.get("case_id") != expected_case):
        raise ValueError("exact original attempt case identity differs")
    if bool(site.get("diagnostic_fixture")) is not diagnostic or (
            bool(provenance.get("diagnostic_fixture")) is not diagnostic):
        raise ValueError("original attempt diagnostic provenance differs")
    if diagnostic:
        if provenance.get("provenance_kind") != "synthetic_fixture":
            raise ValueError("diagnostic fixture provenance differs")
    else:
        if provenance.get("provenance_kind") != "native" or (
                provenance.get("source_site_sha256") != sha(root / "native-site.json")):
            raise ValueError("original Native site provenance differs")
        seal = read(root / "capture-seal.json")
        if (seal.get("provenance_kind") != "native" or seal.get("diagnostic_fixture") is not False or
                seal.get("frames") != 900 or seal.get("restoration", {}).get("restored") is not True or
                seal.get("events") != ["capture_finished", "encoders_closed", "restoration_verified"]):
            raise ValueError("original Native capture seal differs")
        for name in ("native-site.json", "saved-manifest.json", "original-events.json",
                     "trace.jsonl", "video_frames.jsonl", "overview.mkv", "approach.mkv",
                     "reference_corner.mkv", "driver_reference.mkv"):
            if seal.get("sources", {}).get(name) != sha(root / name):
                raise ValueError("sealed original source changed: " + name)
    audited = audit_saved(root, saved)
    if audited["original_frames"] != 900:
        raise ValueError("900 original event frames required")
    event_ref = saved["sources"]["original_events"]
    events = read(root / event_ref["path"])
    trace = rows(root / "trace.jsonl")
    mapping = rows(root / "video_frames.jsonl")
    join_original_frames(events, trace, mapping)
    if any(not isinstance(event.get("other_users"), list) or
           any(user.get("source_kind") != "native_world_snapshot" for user in event["other_users"])
           for event in events):
        raise ValueError("original participant inventory incomplete")
    views = saved["camera_views"]
    for name, size in PROFILE.items():
        if (views[name].get("width"), views[name].get("height"), views[name].get("fps")) != (*size, 20):
            raise ValueError("pinned four-view camera profile differs: " + name)
    media = audit_four_views(root, views, 900)
    manifest = read(HERE / "execution-manifest.json")
    entry = next((item for item in manifest["cases"] if item["case_id"] == expected_case), None)
    if entry is None:
        raise ValueError("selected physical preparation case missing")
    physical = entry["physical_preparation"]
    receipt_path = HERE / physical["receipt"]
    if sha(receipt_path) != physical["sha256"]:
        raise ValueError("physical preparation receipt changed")
    receipt = read(receipt_path)
    if receipt.get("case_id") != expected_case or (
            {item["kind"] for item in receipt.get("fixtures", [])} !=
            {"complete_motion", "incomplete_motion", "missing_evidence"}):
        raise ValueError("physical completion three-outcome proof differs")
    facts = summary(root)
    if facts["duration_frames"] != 900:
        raise ValueError("comparison summary has shortened original capture")
    return {"facts": facts, "case_id": expected_case,
            "saved_manifest_sha256": sha(root / "saved-manifest.json"),
            "native_site_sha256": sha(root / "native-site.json"),
            "original_events_sha256": sha(root / event_ref["path"]),
            "trace_sha256": sha(root / "trace.jsonl"),
            "frame_map_sha256": sha(root / "video_frames.jsonl"),
            "video_sha256": {name: media[name]["sha256"] for name in PROFILE}}


def compare(name, first_root, second_root, diagnostic=False):
    if name not in PAIRS:
        raise ValueError("unknown exact comparison")
    plan = read(HERE / "case-plan.json")
    declared = next((row for row in plan["comparisons"] if row["comparison_id"] == name), None)
    expected = [HERE.name + "__" + suffix for suffix in PAIRS[name][:2]]
    if declared is None or declared.get("case_ids") != expected:
        raise ValueError("declared comparison case pair differs")
    first = attempt(first_root, expected[0], diagnostic)
    second = attempt(second_root, expected[1], diagnostic)
    compared = audit_pair(name, first["facts"], second["facts"])
    return {"format": "c111125-original-comparison-audit", "comparison_id": name,
            "case_ids": expected, "passed": True, "diagnostic_only": diagnostic,
            "physical_acceptance": False, "legal_verdict": None,
            "fixed_conditions": declared["fixed_conditions"],
            "deliberate_differences": declared["deliberate_differences"],
            "fixed_conditions_checked": compared["fixed_conditions_checked"],
            "measured_difference": compared["measured_difference"],
            "attempts": [{key: value for key, value in item.items() if key != "facts"}
                         for item in (first, second)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--first-attempt", type=Path, required=True)
    parser.add_argument("--second-attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if any(output == source.resolve() or source.resolve() in output.parents
           for source in (args.first_attempt, args.second_attempt)):
        raise ValueError("comparison output must be outside original attempts")
    if output.exists():
        raise ValueError("retain prior comparison report")
    result = compare(args.comparison, args.first_attempt, args.second_attempt,
                     diagnostic=args.diagnostic_fixture)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"comparison_id": args.comparison, "passed": True,
                      "diagnostic_only": args.diagnostic_fixture}))


if __name__ == "__main__":
    main()
