"""Exercise source-derived physical outcomes and closure order on CPU fixtures."""
import argparse
import json
import os
import shutil
from pathlib import Path

from worker_exchange.native_output import physical_result, seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, _closure

HERE = Path(__file__).resolve().parent
EXPECTED = {"complete_motion": "met", "incomplete_motion": "not_met", "missing_evidence": "unverified"}


def scratch(name):
    root = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if ".runtime-work" not in root.parts:
        raise ValueError("Physical fixture scratch must be under .runtime-work")
    path = root / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def construction(distance):
    return json.loads((HERE / f"selected-{distance}-primary-construction.json").read_text())


def run_outcome(distance, kind):
    if distance not in (70, 120, 170) or kind not in EXPECTED:
        raise ValueError("Exact distance and physical outcome required")
    root = scratch(f"physical-{distance}-{kind}")
    bundle = construction(distance)
    for item in bundle["files"]:
        if item["path"] == "config.json":
            (root / "config.json").write_text(item["content"])
    source = HERE / "selected-sources" / str(distance)
    for name in ("trace.jsonl", "video_frames.jsonl"):
        shutil.copyfile(source / name, root / name)
    if kind == "incomplete_motion":
        rows = [json.loads(line) for line in (root / "trace.jsonl").read_text().splitlines()]
        fixed = rows[0]["position_m"]
        for row in rows:
            row["position_m"] = fixed
            row["position"] = {"x": fixed[0], "y": fixed[1], "z": fixed[2]}
        (root / "trace.jsonl").write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows))
    if kind == "missing_evidence":
        (root / "trace.jsonl").unlink()
    result = physical_result(root, {
        "case_id": bundle["case_id"], "target_checks": [],
        "physical_acceptance_claimed": False, "legal_acceptance_claimed": False,
    })
    status = result["physical_checks"]["maneuver"]["status"]
    if status != EXPECTED[kind] or result["maneuver_completed"] != (kind == "complete_motion"):
        raise AssertionError(f"Unexpected source-derived physical status {status}")
    if result["provenance_kind"] != "synthetic_fixture" or result["diagnostic_fixture"] is not True:
        raise AssertionError("CPU fixture lost diagnostic provenance")
    dest = HERE / "physical-preparation" / str(distance)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / f"{kind}-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print("PASS", bundle["case_id"], kind, status)


def run_lifecycle(distance):
    if distance not in (70, 120, 170):
        raise ValueError("Exact distance required")
    root = scratch(f"lifecycle-{distance}")
    bundle = construction(distance)
    (root / "construction.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n")
    for item in bundle["files"]:
        if item["path"] in ("config.json", "runner.py"):
            (root / item["path"]).write_text(item["content"])
    source = HERE / "selected-sources" / str(distance)
    for name in ("trace.jsonl", "video_frames.jsonl"):
        shutil.copyfile(source / name, root / name)
    (root / "acquisition-provenance.json").write_text(json.dumps({"diagnostic_fixture": True}) + "\n")
    seal_capture(root, frames=600, restoration={"restored": True}, errors=[], encoder_exit_codes={"overview": 0, "approach": 0, "reference_corner": 0, "driver_reference": 0})
    try:
        acknowledge_owner_release(root, root / "owner-release.json", True)
    except ValueError as error:
        if "Native process has not exited" not in str(error):
            raise
    else:
        raise AssertionError("Owner release preceded Native exit")
    record_native_exit(root)
    acknowledge_owner_release(root, root / "owner-release.json", True)
    _closure(root, root / "owner-release.json", "native", True)
    saved = root / "saved-processing-started.marker"
    saved.write_text("source-closed diagnostic processing\n")
    events = ["capture_finished", "encoders_closed", "restoration_verified", "native_exit", "owner_released", "saved_processing_started"]
    print("PASS", bundle["case_id"], "synthetic lifecycle", json.dumps(events))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--distance", type=int, required=True)
    parser.add_argument("--kind", choices=(*EXPECTED, "lifecycle"), required=True)
    args = parser.parse_args()
    run_lifecycle(args.distance) if args.kind == "lifecycle" else run_outcome(args.distance, args.kind)
