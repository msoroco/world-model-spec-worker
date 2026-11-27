"""Source-bound synthetic CPU motion and ownership diagnostics, with no legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def lifecycle(events):
    required = ["capture_finished", "encoders_closed", "restoration_verified",
                "native_exit", "owner_released", "saved_processing_started"]
    if events != required:
        raise ValueError("Saved processing precedes Native ownership closure")
    return required


def run(case, source, scratch, output):
    from worker_exchange.native_output import physical_result
    source, scratch, output = (Path(value).resolve() for value in (source, scratch, output))
    if scratch.exists():
        raise ValueError("Fresh scratch required")
    scratch.mkdir(parents=True)
    output.mkdir(parents=True, exist_ok=True)
    assignment = Path(__file__).resolve().parents[1]
    base = json.loads((source / "result.json").read_text())
    poses = [json.loads(line) for line in (source / "participant-poses.jsonl").read_text().splitlines()]
    fixtures = []
    for kind, expected in (("complete_motion", "met"), ("incomplete_motion", "not_met"),
                           ("missing_evidence", "unverified")):
        attempt = scratch / kind
        attempt.mkdir()
        for name in ("config.json", "video_frames.jsonl", "trace.jsonl",
                     "acquisition-provenance.json"):
            if (source / name).exists():
                shutil.copyfile(source / name, attempt / name)
        if kind != "missing_evidence":
            altered = []
            for pose in poses:
                row = json.loads(json.dumps(pose))
                if kind == "incomplete_motion":
                    row["ego"]["body_xy_m"] = poses[0]["ego"]["body_xy_m"]
                    row["ego"]["center_xy_m"] = poses[0]["ego"]["center_xy_m"]
                altered.append(row)
            (attempt / "participant-poses.jsonl").write_text("".join(json.dumps(row) + "\n" for row in altered))
        result = physical_result(attempt, dict(base))
        status = result["physical_checks"]["maneuver"]["status"]
        if status != expected or result["maneuver_completed"] != (expected == "met"):
            raise ValueError(f"{kind}: observed {status}, expected {expected}")
        if result["provenance_kind"] != "synthetic_fixture" or result["diagnostic_fixture"] is not True:
            raise ValueError("Synthetic provenance lost")
        result_path = output / f"cpu-{case}-{kind}-result.json"
        log_path = output / f"cpu-{case}-{kind}.log"
        put(result_path, result)
        log_path.write_text(f"{kind}: {status}; generated CPU diagnostic only; no original capture or legal verdict\n")
        fixtures.append({"kind": kind, "command": f"native/prove_physical.py --case {case} --fixture {kind}",
                         "exit_code": 0, "log": str(log_path.relative_to(assignment)),
                         "log_sha256": sha(log_path), "result": str(result_path.relative_to(assignment)),
                         "result_sha256": sha(result_path)})
    ordered = lifecycle(["capture_finished", "encoders_closed", "restoration_verified",
                         "native_exit", "owner_released", "saved_processing_started"])
    try:
        lifecycle(ordered[:-2] + ["saved_processing_started"])
    except ValueError as error:
        if "precedes Native ownership closure" not in str(error):
            raise
    else:
        raise ValueError("Early processing was accepted")
    log = output / f"cpu-{case}-lifecycle.log"
    log.write_text("Generated event-order diagnostic accepts complete order and rejects saved processing before owner release\n")
    proof = {"format": "c272412-physical-preparation-v1", "case_id": case,
             "construction_sha256": sha(assignment / "selected-native-draft" / case.rsplit("__", 1)[-1] / "construction.json"),
             "fixtures": fixtures,
             "lifecycle": {"events": ordered, "exit_code": 0, "log": str(log.relative_to(assignment)),
                           "log_sha256": sha(log), "synthetic_fixture": True,
                           "actual_owner_release_claimed": False},
             "physical_or_legal_acceptance_claimed": False}
    proof_path = output / f"cpu-{case}-physical-preparation.json"
    put(proof_path, proof)
    return proof_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for option in ("case", "source", "scratch", "output"):
        parser.add_argument("--" + option, required=True)
    args = parser.parse_args()
    print(run(args.case, args.source, args.scratch, args.output))
