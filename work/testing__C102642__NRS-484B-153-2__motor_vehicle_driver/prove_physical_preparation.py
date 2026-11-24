"""Exercise three synthetic motion outcomes and the saved lifecycle order."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from delivery_measure import measure


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
KINDS = ("open_near_overlap", "open_near_clear", "open_far_side",
         "board_near", "alight_near")
ACTIONS = {"open_near_overlap": ("open", "left"),
           "open_near_clear": ("open", "left"),
           "open_far_side": ("open", "right"),
           "board_near": ("board", "left"),
           "alight_near": ("alight", "left")}
FIXTURES = ("complete_motion", "incomplete_motion", "missing_evidence")
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(case_id: str, fixture_kind: str, output: Path) -> None:
    kind = case_id.rsplit("__", 1)[-1]
    if kind not in KINDS or case_id != HERE.name + "__" + kind or fixture_kind not in FIXTURES:
        raise ValueError("unknown exact synthetic fixture")
    case = HERE / "cases" / kind
    source = case / "diagnostic-sources/native-trace.json"
    door = case / "diagnostic-sources/door-source.json"
    trace = json.loads(source.read_text())
    intent = json.loads(door.read_text())
    if intent["source_trace_sha256"] != sha(source):
        raise ValueError("synthetic door/trace binding changed")
    act, side = ACTIONS[kind]
    if (intent["selected_act"], intent["selected_side"]) != (act, side):
        raise ValueError("synthetic selected act changed")
    sources = [{"path": str(source.relative_to(REPO)), "sha256": sha(source)},
               {"path": str(door.relative_to(REPO)), "sha256": sha(door)}]
    status = "unverified"
    realized = {}
    if fixture_kind == "complete_motion":
        observed = measure(trace, expected_case_id=case_id,
                           expected_act=act, expected_side=side)
        if not observed["act_frame_ids"] or not observed["body_gap_by_frame_m"]:
            raise ValueError("complete fixture lacks synthetic observed motion")
        status = "met"
        realized = {"observed_act": observed["observed_act"],
                    "act_frame_ids": observed["act_frame_ids"],
                    "minimum_body_gap_m": observed["minimum_body_gap_m"]}
    elif fixture_kind == "incomplete_motion":
        altered = copy.deepcopy(trace)
        for frame in altered["frames"]:
            frame["observed_act"] = "none"
            frame["act_side"] = None
        altered_source = case / "physical" / "incomplete-trace.json"
        write(altered_source, altered)
        sources[0] = {"path": str(altered_source.relative_to(REPO)),
                      "sha256": sha(altered_source)}
        try:
            measure(altered, expected_case_id=case_id,
                    expected_act=act, expected_side=side)
        except ValueError as error:
            if "did not overlap" not in str(error):
                raise
        else:
            raise ValueError("incomplete synthetic motion was accepted")
        status = "not_met"
    else:
        absent = REPO / ".runtime-work/c102642-selected" / f"absent-{kind}-door-source.json"
        if absent.exists():
            raise ValueError("missing-evidence fixture source unexpectedly exists")
        sources[1] = {"path": str(absent), "condition": "absent"}
    write(output, {"case_id": case_id, "fixture_kind": fixture_kind,
                   "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
                   "physical_checks": {"maneuver": {
                       "status": status,
                       "method": "source_bound_synthetic_act_and_body_trace",
                       "sources": sources}},
                   "maneuver_completed": status == "met",
                   "realized_observables": realized,
                   "scope": "CPU classification behavior only; original Native review pending"})
    print(fixture_kind, status, sha(output))


def record() -> None:
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        kind = case_id.rsplit("__", 1)[-1]
        case = HERE / "cases" / kind
        rows = []
        for fixture_kind in FIXTURES:
            result = case / "physical" / (fixture_kind + ".json")
            log = case / "physical" / (fixture_kind + ".log")
            command = [sys.executable, str(HERE / "prove_physical_preparation.py"),
                       "--case", case_id, "--kind", fixture_kind,
                       "--output", str(result)]
            process = subprocess.run(command, cwd=REPO,
                                     env=dict(os.environ, TMPDIR=str(REPO / ".runtime-work"),
                                              PYTHONDONTWRITEBYTECODE="1"),
                                     capture_output=True, text=True)
            log.write_text(process.stdout + process.stderr)
            if process.returncode:
                raise ValueError("physical diagnostic fixture failed: " + kind + ": " + fixture_kind)
            rows.append({"kind": fixture_kind, "command": " ".join(command),
                         "exit_code": process.returncode,
                         "log": str(log.relative_to(HERE)), "log_sha256": sha(log),
                         "result": str(result.relative_to(HERE)),
                         "result_sha256": sha(result)})
        life = case / "physical/lifecycle.log"
        life.write_text("\n".join(EVENTS) + "\n")
        if EVENTS.index("saved_processing_started") <= EVENTS.index("owner_released"):
            raise ValueError("saved processing started before Native ownership release")
        receipt = case / "physical/receipt.json"
        write(receipt, {"format": "worker-physical-preparation",
                        "case_id": case_id,
                        "construction_sha256": entry["construction_sha256"],
                        "fixtures": rows,
                        "lifecycle": {"events": EVENTS, "exit_code": 0,
                                      "log": str(life.relative_to(HERE)),
                                      "log_sha256": sha(life)},
                        "scope": "synthetic CPU classification and lifecycle only"})
        entry["physical_preparation"] = {"receipt": str(receipt.relative_to(HERE)),
                                         "sha256": sha(receipt)}
        print(kind, "synthetic motion classifications passed")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case")
    parser.add_argument("--kind", choices=FIXTURES)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if any(value is not None for value in (args.case, args.kind, args.output)):
        if not all(value is not None for value in (args.case, args.kind, args.output)):
            raise ValueError("one exact fixture requires case, kind and output")
        fixture(args.case, args.kind, args.output)
    else:
        record()


if __name__ == "__main__":
    main()
