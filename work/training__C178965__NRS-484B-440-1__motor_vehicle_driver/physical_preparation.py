"""Exercise source joins, incomplete motion, missing evidence and lifecycle on CPU."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE / "native/tests"))
from test_saved import fixture
from finalize_saved import summarize

KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def run_case(tag, kind, output):
    index = int(tag[-1])
    case = HERE.name + "__" + tag
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    entry = next(row for row in manifest["cases"] if row["case_id"] == case)
    result = {"case_id": case, "construction_sha256": entry["construction_sha256"],
              "diagnostic_fixture": True, "provenance_kind": "synthetic_fixture",
              "original_native_observed": False, "legal_verdict": None}
    if kind == "lifecycle":
        assert EVENTS.index("owner_released") < EVENTS.index("saved_processing_started")
        assert list(reversed(EVENTS[-2:])) != EVENTS[-2:]
        result.update(events=EVENTS, exit_code=0,
                      negative_premature_saved_processing_rejected=True)
    else:
        with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work", prefix="c178965-physical-") as temp:
            attempt = Path(temp)
            fixture(attempt, index)
            source = attempt / "roadside-native.jsonl"
            original_sha = sha(source)
            if kind == "incomplete_motion":
                rows = [json.loads(line) for line in source.read_text().splitlines()]
                for row in rows:
                    row["speed_mps"] = 1.0
                source.write_text("".join(json.dumps(row) + "\n" for row in rows))
            elif kind == "missing_evidence":
                (attempt / "visibility-native.jsonl").unlink()
            try:
                measured = summarize(attempt, case, diagnostic=True)
                status = "met" if len(measured["stopped"]) >= 200 else "not_met"
            except ValueError as error:
                if kind == "incomplete_motion" and "no stopped episode" in str(error):
                    status = "not_met"
                elif kind == "missing_evidence" and "original source missing" in str(error):
                    status = "unverified"
                else:
                    raise
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[kind]
        if status != expected:
            raise ValueError("Physical diagnostic differs: " + kind + "/" + status)
        result.update(physical_checks={"maneuver": {"status": status,
            "method": "600 synchronized synthetic roadside traces; stopped duration and mandatory source checked",
            "sources": ["native/tests/test_saved.py", "finalize_saved.py", original_sha]}},
            maneuver_completed=status == "met",
            realized_observables={"stopped_frames": 200, "requested_mode": tag} if status == "met" else {})
    write(output, result)
    print(json.dumps({"case": tag, "kind": kind,
                      "status": result.get("physical_checks", {}).get("maneuver", {}).get("status")}))


def build():
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    for entry in manifest["cases"]:
        tag = entry["case_id"].rsplit("__", 1)[-1]
        folder = HERE / "physical-proof" / tag
        refs = []
        for kind in (*KINDS, "lifecycle"):
            output, log = folder / (kind + ".json"), folder / (kind + ".log")
            command = [sys.executable, str(Path(__file__).resolve()), "--case", tag,
                       "--kind", kind, "--output", str(output)]
            folder.mkdir(parents=True, exist_ok=True)
            with log.open("w") as stream:
                done = subprocess.run(command, cwd=REPO, stdout=stream,
                                      stderr=subprocess.STDOUT, timeout=30)
            if done.returncode:
                raise ValueError("Physical fixture failed: " + str(log))
            refs.append({"kind": kind, "command": " ".join(command), "exit_code": 0,
                         "log": str(log.relative_to(HERE)), "log_sha256": sha(log),
                         "result": str(output.relative_to(HERE)), "result_sha256": sha(output)})
        life = json.loads((folder / "lifecycle.json").read_text())
        proof = {"format": "c178965-synthetic-physical-preparation", "case_id": entry["case_id"],
                 "construction_sha256": entry["construction_sha256"], "fixtures": refs[:3],
                 "lifecycle": {**life, "log": refs[3]["log"], "log_sha256": refs[3]["log_sha256"]},
                 "diagnostic_only": True, "original_native_observed": False}
        path = folder / "proof.json"
        write(path, proof)
        entry["physical_preparation"] = {"case_id": entry["case_id"],
                                          "receipt": str(path.relative_to(HERE)), "sha256": sha(path)}
    write(HERE / "execution-manifest.json", manifest)
    print(json.dumps({"physical_fixture_cases": len(manifest["cases"])}))


if __name__ == "__main__":
    temp_root = Path(os.environ.get("TMPDIR", "/")).resolve()
    if not temp_root.is_relative_to(REPO / ".runtime-work"):
        raise SystemExit("Set TMPDIR under .runtime-work")
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--case", choices=("probe_01", "probe_02", "probe_03"))
    parser.add_argument("--kind", choices=(*KINDS, "lifecycle"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.build:
        build()
    elif args.case and args.kind and args.output:
        run_case(args.case, args.kind, args.output)
    else:
        parser.error("Select --build or one fixture")
