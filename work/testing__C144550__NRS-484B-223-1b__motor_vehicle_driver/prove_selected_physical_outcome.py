"""Run one synthetic physical outcome through the pinned source-bound checker."""

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCES = ("config.json", "video_frames.jsonl", "trace.jsonl", "lane_history.jsonl", "lane_context.json")
EXPECTED = {"complete_motion": "met", "incomplete_motion": "not_met", "missing_evidence": "unverified"}


def source_for(suffix):
    scratch = ROOT / ".runtime-work"
    if suffix == "left_signal_before_clear_gap":
        return scratch / "c144550-original-first-compat-rebind"
    if suffix == "left_signal_at_departure_clear_gap":
        return scratch / "c144550-zero-primary-compat-final-20261124"
    if suffix.startswith(("left_", "right_")):
        return scratch / ("c144550-original-four-compat-" + suffix)
    if suffix.startswith("signal-"):
        return scratch / ("c144550-selected-compat-current-" + suffix)
    return scratch / ("c144550-selected-compat-" + suffix)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", choices=EXPECTED, required=True)
    args = parser.parse_args()
    output = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
    if not output or not Path(output).resolve().is_relative_to(ROOT / ".runtime-work"):
        raise ValueError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
    if not args.case.startswith(HERE.name + "__"):
        raise ValueError("Case does not belong to C144550")
    from scenario_pipeline.worker_exchange.native_output import physical_result

    suffix = args.case[len(HERE.name) + 2:]
    source = source_for(suffix)
    if not (source / "result.json").is_file():
        raise ValueError("Missing source-bound compatibility result for " + suffix)
    scratch = Path(output) / suffix / args.kind
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    for name in SOURCES:
        shutil.copyfile(source / name, scratch / name)
    if args.kind == "incomplete_motion":
        path = scratch / "lane_history.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines() if line]
        original_lane = rows[0]["ego_lane_id"]
        for row in rows:
            row["ego_lane_id"] = original_lane
        path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    elif args.kind == "missing_evidence":
        (scratch / "lane_history.jsonl").unlink()
    result = json.loads((source / "result.json").read_text())
    for key in ("physical_checks", "physical_observations", "realized_observables"):
        result.pop(key, None)
    result["source_evidence_hashes"] = {
        name: hashlib.sha256((scratch / name).read_bytes()).hexdigest()
        for name in SOURCES if (scratch / name).is_file()
    }
    result = physical_result(scratch, result)
    actual = result["physical_checks"]["maneuver"]["status"]
    if actual != EXPECTED[args.kind]:
        raise ValueError(f"Physical outcome {suffix} {args.kind}: {actual}")
    if result["provenance_kind"] != "synthetic_fixture" or result["diagnostic_fixture"] is not True:
        raise ValueError("Physical outcome lacks synthetic provenance")
    folder = HERE / ("sweep-cases" if "pending-" in suffix else "cases") / suffix
    path = folder / f"physical-{args.kind}.json"
    path.write_text(json.dumps(result, separators=(",", ":"), allow_nan=False) + "\n")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Physical result exceeds return limit")
    print(json.dumps({"case_id": args.case, "kind": args.kind, "status": actual,
                      "result": str(path.relative_to(HERE)),
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                      "synthetic_fixture": True}))


if __name__ == "__main__":
    main()
