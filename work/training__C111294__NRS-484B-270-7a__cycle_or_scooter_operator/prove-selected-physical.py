"""CPU source-shaped motion and owner-release tests; no CARLA observation."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def classify(rows):
    if len(rows) != 600 or any(row.get("native_frame") != 100 + i or
                               not row.get("bicycle", {}).get("body_xy_m") or
                               not row.get("motor_vehicle", {}).get("body_xy_m")
                               for i, row in enumerate(rows)):
        return "unverified"
    first, last = rows[0], rows[-1]
    bicycle = first["bicycle"]["center_xy_m"][1] < -20 and \
        last["bicycle"]["center_xy_m"][1] > 10
    motorist = first["motor_vehicle"]["center_xy_m"][0] < -20 and \
        last["motor_vehicle"]["center_xy_m"][0] > 10
    return "met" if bicycle and motorist else "not_met"


def fixture(case, kind, output):
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    entry = next(x for x in manifest["cases"] if x["case_id"].endswith("__" + case))
    base = {"case_id": entry["case_id"], "construction_sha256": entry["construction_sha256"],
            "diagnostic_fixture": True, "provenance_kind": "synthetic_fixture",
            "original_native_observed": False, "physical_acceptance_claimed": False,
            "legal_verdict_claimed": False}
    if kind == "lifecycle":
        assert EVENTS.index("owner_released") < EVENTS.index("saved_processing_started")
        base.update(events=EVENTS, exit_code=0,
                    negative_premature_saved_processing_rejected=True)
    else:
        source = HERE / "v2-primary" / case / "sources/native_samples.jsonl"
        rows = [json.loads(line) for line in source.read_text().splitlines()]
        if kind == "incomplete_motion":
            for row in rows[100:]:
                row["bicycle"]["center_xy_m"][1] = -12
                row["motor_vehicle"]["center_xy_m"][0] = -12
        elif kind == "missing_evidence":
            rows.pop()
        status = classify(rows)
        assert status == {"complete_motion": "met", "incomplete_motion": "not_met",
                          "missing_evidence": "unverified"}[kind]
        base.update(physical_checks={"maneuver": {
                        "status": status,
                        "method": "600 frame-joined bicycle and separate motor-vehicle body motion",
                        "sources": [source.relative_to(ROOT).as_posix()]}},
                    maneuver_completed=status == "met",
                    realized_observables={"joined_frames": 600,
                                          "source_kind": "synthetic_fixture"} if status == "met" else {},
                    source_sha256=sha(source))
    write(output, base)
    print(json.dumps({"case": case, "kind": kind,
                      "status": base.get("physical_checks", {}).get("maneuver", {}).get("status")}))


def build():
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"].rsplit("__", 1)[-1]
        folder = HERE / "physical-proof" / case
        refs = []
        for kind in (*KINDS, "lifecycle"):
            output, log = folder / (kind + ".json"), folder / (kind + ".log")
            folder.mkdir(parents=True, exist_ok=True)
            command = [sys.executable, str(Path(__file__).resolve()),
                       "--case", case, "--kind", kind, "--output", str(output)]
            with log.open("w") as stream:
                result = subprocess.run(command, cwd=ROOT, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=30)
            if result.returncode:
                raise ValueError("Physical fixture failed: " + str(log))
            refs.append({"kind": kind, "command": " ".join(command), "exit_code": 0,
                         "log": log.relative_to(HERE).as_posix(), "log_sha256": sha(log),
                         "result": output.relative_to(HERE).as_posix(),
                         "result_sha256": sha(output)})
        lifecycle = json.loads((folder / "lifecycle.json").read_text())
        proof = {"format": "c111294-synthetic-physical-preparation-v1",
                 "case_id": entry["case_id"], "construction_sha256": entry["construction_sha256"],
                 "fixtures": refs[:3],
                 "lifecycle": {**lifecycle, "log": refs[3]["log"],
                               "log_sha256": refs[3]["log_sha256"]},
                 "diagnostic_only": True, "original_native_observed": False}
        path = folder / "proof.json"
        write(path, proof)
        entry["physical_preparation"] = {
            "case_id": entry["case_id"], "receipt": path.relative_to(HERE).as_posix(),
            "sha256": sha(path)}
    write(HERE / "execution-manifest.json", manifest)
    print(json.dumps({"physical_cases": len(manifest["cases"])}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--case", choices=("witness_1", "witness_2"))
    parser.add_argument("--kind", choices=(*KINDS, "lifecycle"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.build:
        build()
    elif args.case and args.kind and args.output:
        fixture(args.case, args.kind, args.output)
    else:
        parser.error("Select --build or one fixture")
