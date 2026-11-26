"""CPU physical completion and Native owner-release diagnostic probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work/c130282"
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def run(case_id, kind, output):
    if (case_id not in {row["case_id"] for row in
                        json.loads((HERE / "case-plan.json").read_text())["cases"]} or
            kind not in KINDS):
        raise ValueError("unknown exact physical probe")
    if REPO / ".runtime-work" not in Path(os.environ.get(
            "SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve().parents:
        raise ValueError("direct runtime import requires .runtime-work output root")
    sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
    from worker_exchange.native_output import assess_physical, seal_capture
    from worker_exchange.saved_processing import (record_native_exit,
                                                   acknowledge_owner_release, copy_sources)
    tag = case_id.rsplit("__", 1)[-1]
    construction_path = HERE / "cases" / tag / "construction.json"
    if tag == "inner_right":
        construction_path = HERE / "construction.json"
    construction = json.loads(construction_path.read_text())
    config = json.loads(next(item["content"] for item in construction["files"]
                             if item["path"] == "config.json"))
    with tempfile.TemporaryDirectory(prefix="physical-", dir=SCRATCH) as temporary:
        root = Path(temporary)
        write(root / "config.json", config)
        write(root / "construction.json", construction)
        (root / "runner.py").write_text((HERE / "runner.py").read_text())
        trace, mapping, bodies = [], [], []
        for index in range(9):
            frame, time = 42000 + index, index / 20
            x = index * .5 if kind == "complete_motion" else 0.0
            trace.append({"frame": frame, "time_s": time,
                          "position_m": [x, 0, 0], "speed_mps": 0.0})
            mapping.append({"video_frame": index, "carla_frame": frame,
                            "native_frame": frame, "time_s": time})
            bodies.append({"frame": frame, "time_s": time,
                           "body_vertices_m": [[x-1, -1, 0], [x+1, -1, 0],
                                               [x+1, 1, 0], [x-1, 1, 0]]})
        for name, rows in (("trace.jsonl", trace), ("video_frames.jsonl", mapping),
                           ("body_history.jsonl", bodies)):
            with (root / name).open("x") as stream:
                for row in rows:
                    stream.write(json.dumps(row, sort_keys=True) + "\n")
        if kind == "missing_evidence":
            (root / "config.json").unlink()
        assessment = assess_physical(root, config)
        status = assessment["physical_checks"]["maneuver"]["status"]
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[kind]
        if status != expected:
            raise ValueError("physical fixture classification changed: " + status)
        result = {"case_id": case_id, "physical_checks": assessment["physical_checks"],
                  "maneuver_completed": assessment["maneuver_completed"],
                  "realized_observables": assessment["realized_observables"],
                  "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
                  "physical_acceptance_claimed": False, "legal_judgment": None}
        write(Path(output), result)
        events = None
        if kind == "complete_motion":
            write(root / "acquisition-provenance.json", {
                "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
                "physical_acceptance_claimed": False})
            sealed = seal_capture(root, frames=9, restoration={"restored": True},
                                  errors=[], encoder_exit_codes={"diagnostic": 0})
            native_exit = record_native_exit(root)
            owner = acknowledge_owner_release(root, root / "owner-release.json", True)
            with tempfile.TemporaryDirectory(prefix="saved-", dir=SCRATCH) as saved:
                copy_sources(root, Path(saved))
            if (native_exit["capture_seal_sha256"] != sha(root / "capture-seal.json") or
                    owner["native_exit_sha256"] != sha(root / "native-exit.json")):
                raise ValueError("Native owner-release chain changed")
            events = sealed["events"] + ["native_exit", "owner_released",
                                          "saved_processing_started"]
        return {"case_id": case_id, "kind": kind, "status": status,
                "events": events, "diagnostic_fixture": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", choices=KINDS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.kind, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
