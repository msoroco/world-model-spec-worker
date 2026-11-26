"""CPU physical-motion and ownership-order fixtures for the exact speed pair."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
REPO = FOLDER.parents[1]
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def evaluate(rows):
    if len(rows) != 600 or any(row.get("video_frame") != i or
                                row.get("native_frame") != 3000 + i or
                                abs(row.get("time_s", -1) - i / 20) > 1e-6
                                for i, row in enumerate(rows)):
        return "unverified", {}
    if any(row.get("source_kind") != "synthetic_cpu_fixture" or
           not isinstance(row.get("ego", {}).get("road_x_m"), (int, float)) for row in rows):
        return "unverified", {}
    travel = rows[-1]["ego"]["road_x_m"] - rows[0]["ego"]["road_x_m"]
    return ("met" if travel > 0.25 else "not_met"), {
        "joined_frames": 600, "observed_travel_m": round(travel, 5),
        "engineering_minimum_progress_m": 0.25,
        "not_a_legal_threshold": True}


def fixture(suffix, kind, output):
    case = FOLDER.name + "__selected_d6045110__condition_" + suffix
    construction = HERE / "selected" / suffix / "construction.json"
    result = {"case_id": case, "construction_sha256": sha(construction),
              "diagnostic_fixture": True, "provenance_kind": "synthetic_fixture",
              "original_native_observed": False, "legal_outcome_claimed": False}
    if kind == "lifecycle":
        processing = json.loads((HERE / ("selected-" + suffix + "-proof/processing.json")).read_text())
        if not (processing.get("passed") and processing.get("recorded_only")
                and processing.get("originals_preserved") and
                "saved_processing_started" in processing.get("events", [])):
            raise ValueError("Recorded-only lifecycle source missing")
        premature = EVENTS[:-2] + list(reversed(EVENTS[-2:]))
        if premature.index("saved_processing_started") > premature.index("owner_released"):
            raise ValueError("Premature saved processing was not rejected")
        result.update(events=EVENTS, exit_code=0,
                      negative_premature_saved_processing_rejected=True,
                      recorded_only_receipt_sha256=sha(HERE / ("selected-" + suffix + "-proof/processing.json")))
    else:
        source = FOLDER / "selected-fixture-sources" / suffix / "emergency_observations.jsonl"
        rows = [json.loads(line) for line in source.read_text().splitlines()]
        if kind == "incomplete_motion":
            rows = copy.deepcopy(rows)
            first = rows[0]["ego"]["road_x_m"]
            for row in rows:
                row["ego"]["road_x_m"] = first
        elif kind == "missing_evidence":
            rows.pop()
        status, measured = evaluate(rows)
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[kind]
        if status != expected:
            raise ValueError("Physical fixture status differs: " + kind + "/" + status)
        result.update(physical_checks={"maneuver": {"status": status,
                       "method": "600 original-shaped time-joined synthetic actor positions; engineering progress only",
                       "sources": {str(source.relative_to(REPO)): sha(source)}}},
                      maneuver_completed=status == "met",
                      realized_observables=measured if status == "met" else {})
    write(output, result)
    print(json.dumps({"case_id": case, "kind": kind,
                      "status": result.get("physical_checks", {}).get("maneuver", {}).get("status")}))


def build():
    index = []
    for suffix in "ab":
        case = FOLDER.name + "__selected_d6045110__condition_" + suffix
        directory = HERE / "physical-proof" / suffix
        directory.mkdir(parents=True, exist_ok=True)
        refs = []
        for kind in (*KINDS, "lifecycle"):
            output = directory / (kind + ".json")
            log = directory / (kind + ".log")
            command = [sys.executable, "-B", str(Path(__file__).resolve()),
                       "--case", suffix, "--kind", kind, "--output", str(output)]
            done = subprocess.run(command, cwd=REPO, capture_output=True, text=True,
                                  env=os.environ.copy(), timeout=30)
            log.write_text("\n".join(line.rstrip() for line in
                                      (done.stdout + done.stderr).splitlines()).rstrip() + "\n")
            if done.returncode:
                raise ValueError("Physical fixture failed: " + str(log))
            refs.append({"kind": kind, "command": " ".join(command), "exit_code": 0,
                         "log": str(log.relative_to(FOLDER)), "log_sha256": sha(log),
                         "result": str(output.relative_to(FOLDER)), "result_sha256": sha(output)})
        life = json.loads((directory / "lifecycle.json").read_text())
        proof = {"format": "c405647-2a-synthetic-physical-preparation",
                 "case_id": case,
                 "construction_sha256": sha(HERE / "selected" / suffix / "construction.json"),
                 "fixtures": refs[:3],
                 "lifecycle": dict(life, log=refs[3]["log"], log_sha256=refs[3]["log_sha256"]),
                 "diagnostic_only": True, "original_native_observed": False}
        path = directory / "proof.json"
        write(path, proof)
        index.append({"case_id": case, "receipt": str(path.relative_to(FOLDER)),
                      "sha256": sha(path)})
    write(HERE / "physical-proof/index.json", {"cases": index, "diagnostic_only": True})
    print(json.dumps({"physical_fixture_cases": len(index)}))


if __name__ == "__main__":
    if not Path(os.environ.get("TMPDIR", "/")).resolve().is_relative_to(REPO / ".runtime-work"):
        raise SystemExit("Set TMPDIR under .runtime-work")
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--case", choices=("a", "b"))
    parser.add_argument("--kind", choices=(*KINDS, "lifecycle"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.build:
        build()
    elif args.case and args.kind and args.output:
        fixture(args.case, args.kind, args.output)
    else:
        parser.error("Choose --build or one exact fixture")
