"""Exercise physical completion and closure checks with synthetic CPU sources.

These fixtures test software classification only. They do not show actual CARLA
motion, camera visibility, lawful movement, or physical acceptance.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


ASSIGNMENT = "testing__C111125__NRS-484B-307-8d__cycle_or_scooter_operator"
ROOT = Path(__file__).resolve().parents[1].parent
RUNTIME = ROOT / "runtime" / "scenario_pipeline"


def runtime_modules():
    output_root = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
    if not output_root or ROOT / "runtime" in Path(output_root).resolve().parents:
        raise ValueError("set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
    sys.path.insert(0, str(RUNTIME))
    from worker_exchange import native_output, saved_processing
    return native_output, saved_processing


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def construction_info(path: Path, case: str):
    construction = json.loads(path.read_text(encoding="utf-8"))
    if construction.get("case_id") != case or not case.startswith(ASSIGNMENT + "__"):
        raise ValueError("physical fixture case/construction identity differs")
    files = {item["path"]: item["content"] for item in construction["files"]}
    config = json.loads(files["config.json"])
    return construction, config, files["runner.py"]


def make_sources(scratch: Path, construction_path: Path, case: str, kind: str) -> Path:
    construction, config, runner = construction_info(construction_path, case)
    if scratch.exists():
        raise ValueError("retain prior physical fixture; choose fresh scratch")
    scratch.mkdir(parents=True)
    write_json(scratch / "config.json", config)
    write_json(scratch / "construction.json", construction)
    (scratch / "runner.py").write_text(runner, encoding="utf-8")
    write_json(scratch / "acquisition-provenance.json",
               {"provenance_kind": "synthetic_fixture", "diagnostic_fixture": True})
    mapping = []
    trace = []
    span = 120.0 if kind == "complete_motion" else 50.0
    for i in range(900):
        frame = i + 1
        time_s = i / 20
        mapping.append({"carla_frame": frame, "time_s": time_s, "video_frame": i})
        trace.append({"frame": frame, "time_s": time_s,
                      "position_m": [span * i / 899, 0.0, 0.0]})
    (scratch / "video_frames.jsonl").write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in mapping) + "\n",
        encoding="utf-8")
    if kind != "missing_evidence":
        (scratch / "trace.jsonl").write_text(
            "\n".join(json.dumps(row, sort_keys=True) for row in trace) + "\n",
            encoding="utf-8")
    return scratch


def outcome(native_output, scratch: Path, kind: str, result_path: Path) -> None:
    result = native_output.physical_result(scratch, {"target_checks": []})
    expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                "missing_evidence": "unverified"}[kind]
    actual = result["physical_checks"]["maneuver"]["status"]
    if actual != expected or result["maneuver_completed"] != (expected == "met"):
        raise ValueError("physical outcome classifier differs: " + actual)
    if result["provenance_kind"] != "synthetic_fixture" or result["diagnostic_fixture"] is not True:
        raise ValueError("physical fixture provenance differs")
    if result.get("physical_acceptance_claimed") is not False:
        raise ValueError("physical fixture claimed acceptance")
    write_json(result_path, result)
    print(json.dumps({"kind": kind, "status": actual, "case_id":
                      json.loads((scratch / "config.json").read_text())["selected_case_id"],
                      "diagnostic_fixture": True, "physical_acceptance_claimed": False},
                     sort_keys=True))


def lifecycle(native_output, saved_processing, scratch: Path) -> None:
    # The fixture never owns a simulator. It exercises the same closure receipt
    # validators that gate saved processing after a real Native process exits.
    seal = native_output.seal_capture(
        scratch, frames=900, restoration={"restored": True}, errors=[],
        encoder_exit_codes={name: 0 for name in
                            ("overview", "approach", "reference_corner", "driver_reference")})
    if seal["events"] != ["capture_finished", "encoders_closed", "restoration_verified"]:
        raise ValueError("capture closure ordering differs")
    saved_processing.record_native_exit(scratch)
    release = scratch / "owner-release.json"
    saved_processing.acknowledge_owner_release(scratch, release, True)
    saved_processing._closure(scratch, release, "native", True)
    events = seal["events"] + ["native_exit", "owner_released", "saved_processing_started"]
    print(json.dumps({"events": events, "diagnostic_fixture": True,
                      "physical_acceptance_claimed": False}, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--construction", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--kind", choices=("complete_motion", "incomplete_motion",
                                          "missing_evidence", "lifecycle"), required=True)
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    native_output, saved_processing = runtime_modules()
    source_kind = "complete_motion" if args.kind == "lifecycle" else args.kind
    scratch = make_sources(args.scratch, args.construction, args.case, source_kind)
    if args.kind == "lifecycle":
        lifecycle(native_output, saved_processing, scratch)
    else:
        if args.result is None:
            raise ValueError("physical outcome result path required")
        outcome(native_output, scratch, args.kind, args.result)


if __name__ == "__main__":
    main()
