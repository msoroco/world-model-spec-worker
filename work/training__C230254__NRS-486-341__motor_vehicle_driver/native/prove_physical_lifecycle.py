"""Exercise source-bound lane motion and Native closure using CPU fixtures."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
SCRATCH = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) / "c230254-physical"
sys.path.insert(0, str(REPO / "runtime"))
from scenario_pipeline.worker_exchange.native_output import seal_capture
from scenario_pipeline.worker_exchange.saved_processing import _closure, acknowledge_owner_release, record_native_exit
from physical_audit import assess
from test_comparison_audit import make_case


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def fixture(case, kind):
    suffix = case.rsplit("__", 1)[-1]
    attempt = SCRATCH / suffix / kind
    if attempt.exists():
        import shutil
        shutil.rmtree(attempt)
    attempt.parent.mkdir(parents=True, exist_ok=True)
    make_case(attempt, suffix, suffix, 4 if suffix == "full_lane_available" else 1)
    if kind == "missing_evidence":
        (attempt / "lane-use-source.jsonl").unlink()
        try:
            assess(attempt)
        except ValueError as error:
            if "Missing required source" not in str(error):
                raise
            check = {"status": "unverified", "method": "original source-bound full-footprint path",
                     "sources": ["lane-use-source.jsonl missing"], "error": str(error)}
        else:
            raise AssertionError("Missing original geometry accepted")
    else:
        check = assess(attempt, minimum_progress_m=0.25 if kind == "complete_motion" else 1000.0)
        expected = "met" if kind == "complete_motion" else "not_met"
        if check["status"] != expected:
            raise AssertionError("Source path motion status differs")
        check = {"status": check["status"], "method": check["method"],
                 "sources": check["sources"], "observed": check["observed"],
                 "minimum_progress_m": check["minimum_progress_m"]}
    status = check["status"]
    result = {"case_id": case, "physical_checks": {"maneuver": check},
              "maneuver_completed": status == "met",
              "realized_observables": {"subject_path_m": {"value": check["observed"]["subject_path_m"], "unit": "m"}} if status == "met" else {},
              "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
              "legal_verdict_claimed": False}
    evidence = ROOT / "physical" / suffix
    result_path = evidence / (kind + "-result.json")
    log_path = evidence / (kind + ".log")
    write(result_path, result)
    log_path.write_text(f"{case} {kind}: source-bound physical motion={status}; diagnostic fixture only\n")
    return {"kind": kind,
            "command": f"SCENARIO_PIPELINE_OUTPUT_ROOT=.runtime-work .venv-cpu/bin/python -B work/{ROOT.name}/native/prove_physical_lifecycle.py --case {case} --kind {kind}",
            "exit_code": 0, "log": str(log_path.relative_to(ROOT)), "log_sha256": sha(log_path),
            "result": str(result_path.relative_to(ROOT)), "result_sha256": sha(result_path)}


def lifecycle(case, construction_path):
    suffix = case.rsplit("__", 1)[-1]
    attempt = SCRATCH / suffix / "lifecycle"
    if attempt.exists():
        import shutil
        shutil.rmtree(attempt)
    attempt.mkdir(parents=True, exist_ok=True)
    (attempt / "trace.jsonl").write_text('{"frame":2000,"time_s":0,"position_m":[0,0,0]}\n')
    (attempt / "video_frames.jsonl").write_text('{"video_frame":0,"carla_frame":2000,"native_frame":2000,"time_s":0}\n')
    (attempt / "construction.json").write_bytes(construction_path.read_bytes())
    (attempt / "runner.py").write_text("# Diagnostic closure fixture.\n")
    write(attempt / "acquisition-provenance.json", {"provenance_kind": "synthetic_fixture", "diagnostic_fixture": True})
    seal = seal_capture(attempt, frames=1, restoration={"restored": True}, errors=[], encoder_exit_codes={"overview": 0})
    if seal["events"] != ["capture_finished", "encoders_closed", "restoration_verified"]:
        raise AssertionError("Capture seal order changed")
    record_native_exit(attempt)
    release = attempt / "owner-release.json"
    acknowledge_owner_release(attempt, release, True)
    _closure(attempt, release, "native", False)
    try:
        _closure(attempt, None, "native", False)
    except ValueError as error:
        if "owner-release" not in str(error):
            raise
    else:
        raise AssertionError("Absent owner release accepted")
    evidence = ROOT / "physical" / suffix / "lifecycle.log"
    evidence.write_text(f"{case}: capture, encoder closure, restoration, Native exit, owner release; absent release rejected\n")
    return {"events": ["capture_finished", "encoders_closed", "restoration_verified", "native_exit", "owner_released", "saved_processing_started"],
            "exit_code": 0, "log": str(evidence.relative_to(ROOT)), "log_sha256": sha(evidence)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", choices=("complete_motion", "incomplete_motion", "missing_evidence"))
    args = parser.parse_args()
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    row = next(item for item in manifest["cases"] if item["case_id"] == args.case)
    kinds = [args.kind] if args.kind else ["complete_motion", "incomplete_motion", "missing_evidence"]
    fixtures = [fixture(args.case, kind) for kind in kinds]
    if args.kind:
        print(json.dumps({"case": args.case, "kind": args.kind, "passed": True}))
        return
    life = lifecycle(args.case, ROOT / row["construction"])
    receipt = {"format": "worker-nrs486-341-physical-preparation-v1", "case_id": args.case,
               "construction_sha256": row["construction_sha256"], "fixtures": fixtures,
               "lifecycle": life, "scope": "synthetic CPU checker and closure protocol only"}
    write(ROOT / "physical" / args.case.rsplit("__", 1)[-1] / "receipt.json", receipt)
    print(json.dumps({"case": args.case, "passed": True}))


if __name__ == "__main__":
    main()
