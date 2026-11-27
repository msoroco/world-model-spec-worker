"""Synthetic motion and missing-source lifecycle proof for freight curb requests."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def ordered_events(events):
    expected = ["capture_finished", "encoders_closed", "restoration_verified",
                "native_exit", "owner_released", "saved_processing_started"]
    if events != expected:
        raise ValueError("Saved processing precedes Native ownership closure")
    return events


def prove(case_id, source, scratch, output):
    from worker_exchange.native_output import physical_result
    source, scratch, output = (Path(value).resolve() for value in (source, scratch, output))
    if scratch.exists():
        raise ValueError("Use fresh .runtime-work physical scratch")
    scratch.mkdir(parents=True)
    output.mkdir(parents=True, exist_ok=True)
    trace = [json.loads(line) for line in (source / "trace.jsonl").read_text().splitlines()]
    baseline = json.loads((source / "result.json").read_text())
    fixtures = []
    for kind, expected in (("complete_motion", "met"),
                           ("incomplete_motion", "not_met"),
                           ("missing_evidence", "unverified")):
        attempt = scratch / kind
        attempt.mkdir()
        for name in ("config.json", "video_frames.jsonl"):
            shutil.copyfile(source / name, attempt / name)
        if kind != "missing_evidence":
            rows = trace if kind == "complete_motion" else []
            if kind == "incomplete_motion":
                for row in trace:
                    changed = dict(row)
                    changed["position"] = dict(trace[0]["position"])
                    changed["position_m"] = list(trace[0]["position_m"])
                    rows.append(changed)
            (attempt / "trace.jsonl").write_text("".join(
                json.dumps(row, allow_nan=False) + "\n" for row in rows))
        result = physical_result(attempt, dict(baseline))
        observed = result["physical_checks"]["maneuver"]["status"]
        if observed != expected or result["maneuver_completed"] != (expected == "met"):
            raise ValueError("Physical fixture classification differs: " + kind + " " + observed)
        if result["provenance_kind"] != "synthetic_fixture" or result["diagnostic_fixture"] is not True:
            raise ValueError("Physical fixture provenance changed")
        result_path = output / (kind + ".json")
        log_path = output / (kind + ".log")
        put(result_path, result)
        log_path.write_text(kind + ": " + observed + "; synthetic only, no legal verdict\n")
        fixtures.append({"kind": kind, "command": "prove_physical.py --case " + case_id +
            " --fixture " + kind, "exit_code": 0,
            "log": str(log_path.relative_to(HERE)), "log_sha256": sha(log_path),
            "result": str(result_path.relative_to(HERE)), "result_sha256": sha(result_path)})
    good = ordered_events(["capture_finished", "encoders_closed", "restoration_verified",
                           "native_exit", "owner_released", "saved_processing_started"])
    try:
        ordered_events(good[:-2] + ["saved_processing_started"])
    except ValueError:
        pass
    else:
        raise ValueError("Early saved processing unexpectedly accepted")
    life_log = output / "lifecycle.log"
    life_log.write_text("Synthetic complete lifecycle accepted; early saved processing rejected\n")
    lifecycle = {"events": good, "exit_code": 0,
        "log": str(life_log.relative_to(HERE)), "log_sha256": sha(life_log),
        "synthetic_fixture": True, "actual_owner_release_claimed": False}
    construction = HERE / "selected" / case_id.rsplit("__", 1)[-1] / "construction.json"
    receipt = {"format": "worker-freight-curb-physical-preparation",
        "case_id": case_id, "construction_sha256": sha(construction),
        "fixtures": fixtures, "lifecycle": lifecycle,
        "physical_or_legal_acceptance_claimed": False}
    receipt_path = output / "proof.json"
    put(receipt_path, receipt)
    return {"case_id": case_id, "receipt": str(receipt_path.relative_to(HERE)),
            "sha256": sha(receipt_path)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--scratch", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(prove(args.case, args.source, args.scratch, args.output), sort_keys=True))
