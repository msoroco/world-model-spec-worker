"""Exercise exact-case delivery audit boundaries with source-bound CPU fixtures."""

import argparse
import json
import os
import shutil
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def source_for(suffix):
    scratch = ROOT / ".runtime-work"
    if suffix == "left_signal_before_clear_gap":
        return scratch / "c144550-original-first-compat-rebind"
    if suffix == "left_signal_at_departure_clear_gap":
        return scratch / "c144550-zero-primary-compat-final-20261124"
    if suffix.startswith(("left_", "right_")):
        return scratch / ("c144550-original-four-compat-" + suffix)
    if suffix in ("signal-appropriateness-pending-0001", "safety-ascertainment-pending-0001"):
        return scratch / ("c144550-source-fix-compat-" + suffix)
    if suffix.startswith("signal-"):
        return scratch / ("c144550-selected-compat-current-" + suffix)
    return scratch / ("c144550-selected-compat-" + suffix)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--mode", choices=("positive", "negative"), required=True)
    args = parser.parse_args()
    output = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
    if not output or not Path(output).resolve().is_relative_to(ROOT / ".runtime-work"):
        raise ValueError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
    from delivery_acceptance import CHECKS, audit_sources, read, selected, verify_physical

    entry = selected(args.case)
    suffix = args.case.split("__")[-1]
    source = source_for(suffix)
    result = read(source / "result.json")
    if result.get("case_id") != entry["case_id"] or result.get("provenance_kind") != "synthetic_fixture":
        raise ValueError("CPU source identity or diagnostic provenance differs")
    source_audit = audit_sources(source, args.case)
    if source_audit["original_frame_count"] != 900:
        raise ValueError("Expected 900 original diagnostic frames")
    folder = Path(output) / "acceptance" / suffix / args.mode
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    physical_sources = result["physical_checks"]["maneuver"]["sources"]
    for name in physical_sources:
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
    verify_physical(result, folder)
    if args.mode == "negative":
        with (folder / "lane_history.jsonl").open("a") as stream:
            stream.write('{"tampered":true}\n')
        verify_physical(result, folder)
        raise AssertionError("Tampered physical source incorrectly accepted")
    print(json.dumps({"case_id": args.case, "mode": args.mode,
                      "implemented_auditor_checks": CHECKS,
                      "cpu_tested_checks": ["all_participants", "time_join", "physical_completion"],
                      "original_frame_count": source_audit["original_frame_count"],
                      "diagnostic_fixture": True,
                      "native_or_pixel_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
