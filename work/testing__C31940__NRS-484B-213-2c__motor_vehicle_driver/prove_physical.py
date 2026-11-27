"""CPU source-shaped physical outcome and lifecycle probes; no CARLA motion claim."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))


def _write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def physical(case, kind, output):
    from worker_exchange.fixture_recipe import materialize
    from worker_exchange.native_output import physical_result
    root = ROOT / "work/testing__C31940__NRS-484B-213-2c__motor_vehicle_driver"
    variant = case.removeprefix(root.name + "__")
    if variant == case or kind not in ("complete_motion", "incomplete_motion", "missing_evidence"):
        raise ValueError("exact case/physical kind required")
    recipe = root / f"fixture-recipe-{variant}.json"
    with tempfile.TemporaryDirectory(dir=ROOT / ".runtime-work", prefix="c31940-physical-") as tmp:
        attempt = Path(tmp) / "attempt"
        materialize(ROOT, recipe, attempt)
        cfg = root / ("config.json" if variant == "obstructed_beyond_100ft" else f"cases/{variant}/config.json")
        shutil.copyfile(cfg, attempt / "config.json")
        path = attempt / "trace.jsonl"
        if kind == "missing_evidence":
            path.unlink()
        else:
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            for i, row in enumerate(rows):
                row["position_m"] = [20.0*i/(len(rows)-1) if kind == "complete_motion" else 0.1*i, 0.0]
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        source = json.loads((attempt / "native-result.json").read_text())
        result = physical_result(attempt, source)
        expected = {"complete_motion":"met", "incomplete_motion":"not_met",
                    "missing_evidence":"unverified"}[kind]
        if result["physical_checks"]["maneuver"]["status"] != expected:
            raise ValueError("physical criterion result differs from original-shaped fixture: " +
                             str(result["physical_checks"]["maneuver"]))
        if result["maneuver_completed"] != (expected == "met"):
            raise ValueError("physical completion Boolean differs from source check")
        _write(output, result)
        print(json.dumps({"case_id":case,"kind":kind,"status":expected,
                          "original_source_sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None,
                          "diagnostic_fixture":True}, sort_keys=True))


def lifecycle(case, output):
    from worker_exchange.saved_processing import _closure, record_native_exit, acknowledge_owner_release
    root = ROOT / ".runtime-work"
    with tempfile.TemporaryDirectory(dir=root, prefix="c31940-lifecycle-") as tmp:
        attempt = Path(tmp)
        (attempt / "construction.json").write_text("{}\n")
        (attempt / "runner.py").write_text("# lifecycle source\n")
        seal = {"events":["capture_finished","encoders_closed","restoration_verified"],
                "sources":{},"native_revision":{"construction_sha256":hashlib.sha256((attempt / "construction.json").read_bytes()).hexdigest(),
                                                   "runner_sha256":hashlib.sha256((attempt / "runner.py").read_bytes()).hexdigest()}}
        _write(attempt / "capture-seal.json", seal)
        premature = False
        try:
            _closure(attempt, None, "native", False)
        except (ValueError, FileNotFoundError) as error:
            premature = "native-exit.json" in str(error) or "Native process has not exited" in str(error) or "Supply an operator owner-release" in str(error)
        if not premature:
            raise ValueError("premature saved processing was not rejected")
        _write(attempt / "native-exit.json", record_native_exit(attempt))
        owner = attempt / "owner-release-attested.json"
        acknowledge_owner_release(attempt, owner, True)
        _closure(attempt, owner, "native", False)
        events = seal["events"] + ["native_exit","owner_released","saved_processing_started"]
        _write(output, {"case_id":case,"events":events,"exit_code":0,"premature_rejected":True,
                        "source":"runtime saved_processing closure and owner-release checkers"})
        print(json.dumps({"case_id":case,"events":events,"premature_rejected":True}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case")
    parser.add_argument("--kind", choices=("complete_motion","incomplete_motion","missing_evidence"))
    parser.add_argument("--lifecycle", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.lifecycle:
        if not args.case:
            parser.error("--case required for lifecycle proof")
        lifecycle(args.case, args.output)
    else:
        if not args.case or not args.kind:
            parser.error("--case and --kind required")
        physical(args.case,args.kind,args.output)


if __name__ == "__main__":main()
