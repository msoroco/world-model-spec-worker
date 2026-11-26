"""Source-shaped physical crossing and ownership-order CPU proofs."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from worker_exchange.native_output import physical_result
from worker_exchange.saved_processing import _closure

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CASE = "training__C111325__NRS-484B-257-1__motor_vehicle_driver__yield_sign_no_slow_conflict"
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def one(kind, output):
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    entry = next(item for item in manifest["cases"] if item["case_id"] == CASE)
    base = {"case_id": CASE, "construction_sha256": entry["construction_sha256"],
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "original_native_observed": False, "physical_acceptance_claimed": False}
    if kind == "lifecycle":
        scratch = REPO / ".runtime-work" / "nrs257-physical-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="closure-", dir=scratch) as temporary:
            try:
                _closure(Path(temporary), None, "native", False)
            except ValueError as error:
                if "owner-release receipt" not in str(error):
                    raise
            else:
                raise AssertionError("Premature Native saved processing was accepted")
        saved = json.loads((HERE / "saved/yield_sign_no_slow_conflict-processing.json").read_text())
        if saved.get("recorded_only") is not True or saved.get("passed") is not True:
            raise ValueError("Recorded-only diagnostic processing receipt missing")
        base.update(events=EVENTS, exit_code=0, premature_saved_processing_rejected=True,
                    recorded_only_diagnostic_receipt_sha256=sha(HERE / "saved/yield_sign_no_slow_conflict-processing.json"))
    else:
        scratch = REPO / ".runtime-work" / "nrs257-physical-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="crossing-", dir=scratch) as temporary:
            root = Path(temporary)
            source = HERE / "selected-source/yield_sign_no_slow_conflict"
            for name in ("trace.jsonl", "video_frames.jsonl", "interaction_history.jsonl",
                         "control_context.json", "acquisition-provenance.json"):
                shutil.copyfile(source / name, root / name)
            shutil.copyfile(HERE / "config-yield_sign_no_slow_conflict.json", root / "config.json")
            if kind == "incomplete_motion":
                interactions = [json.loads(line) for line in (root / "interaction_history.jsonl").read_text().splitlines()]
                traces = [json.loads(line) for line in (root / "trace.jsonl").read_text().splitlines()]
                for row, trace in zip(interactions, traces):
                    original_x = [vertex[0] for vertex in row["ego"]["body_vertices_m"]]
                    offset = -45 - (min(original_x) + max(original_x)) / 2
                    for vertex in row["ego"]["body_vertices_m"]:
                        vertex[0] += offset
                    trace["position"]["x"] = -45
                    trace["position_m"][0] = -45
                    trace["speed_mps"] = 0
                (root / "interaction_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in interactions))
                (root / "trace.jsonl").write_text("".join(json.dumps(row) + "\n" for row in traces))
            if kind == "missing_evidence":
                (root / "interaction_history.jsonl").unlink()
            assessed = physical_result(root, {"target_checks": [{"matched": True}]})
            expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                        "missing_evidence": "unverified"}[kind]
            observed = assessed["physical_checks"]["maneuver"]["status"]
            if observed != expected or assessed["maneuver_completed"] is not (expected == "met"):
                raise ValueError("Physical fixture outcome differs: " + kind + "/" + observed)
            base.update({key: assessed[key] for key in ("physical_checks", "maneuver_completed",
                                                    "realized_observables")})
    write(output, base)
    print(json.dumps({"case_id": CASE, "kind": kind,
                      "maneuver_status": base.get("physical_checks", {}).get("maneuver", {}).get("status")}))


def build():
    entry = next(item for item in json.loads((HERE / "execution-manifest.json").read_text())["cases"]
                 if item["case_id"] == CASE)
    folder = HERE / "physical-proof/yield_sign_no_slow_conflict"
    refs = []
    for kind in (*KINDS, "lifecycle"):
        output = folder / (kind + ".json")
        log = folder / (kind + ".log")
        command = [sys.executable, "-B", str(Path(__file__).resolve()), "--kind", kind,
                   "--output", str(output)]
        folder.mkdir(parents=True, exist_ok=True)
        with log.open("w") as stream:
            completed = subprocess.run(command, cwd=REPO, env=os.environ,
                                       stdout=stream, stderr=subprocess.STDOUT, timeout=90)
        log.write_text(log.read_text().rstrip() + "\n")
        if completed.returncode:
            raise ValueError("Physical fixture failed: " + str(log))
        refs.append({"kind": kind, "command": " ".join(command), "exit_code": 0,
                     "log": str(log.relative_to(HERE)), "log_sha256": sha(log),
                     "result": str(output.relative_to(HERE)), "result_sha256": sha(output)})
    life = json.loads((folder / "lifecycle.json").read_text())
    proof = {"format": "nrs-484b-257-1-physical-cpu-v1", "case_id": CASE,
             "construction_sha256": entry["construction_sha256"],
             "fixtures": refs[:3],
             "lifecycle": {**life, "log": refs[3]["log"], "log_sha256": refs[3]["log_sha256"]},
             "diagnostic_only": True, "original_native_observed": False}
    write(folder / "proof.json", proof)
    print(json.dumps({"case_id": CASE, "physical_cpu_fixtures": 3, "lifecycle_cpu": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--kind", choices=(*KINDS, "lifecycle"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.build:
        build()
    elif args.kind and args.output:
        one(args.kind, args.output)
    else:
        parser.error("Use --build or --kind with --output")
