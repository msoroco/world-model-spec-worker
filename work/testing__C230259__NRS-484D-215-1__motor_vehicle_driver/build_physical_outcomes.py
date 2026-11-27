"""Prove source-bound synthetic complete, incomplete and missing motion outcomes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from worker_exchange.native_output import physical_result

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PLAN = json.loads((ROOT / "case-plan.json").read_text())
SCRATCH = REPO / ".runtime-work" / "c230259-physical"
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def source_rows(kind):
    count = 900
    mapping = []
    trace = []
    for index in range(count):
        frame, time = 20000 + index, index / 20
        distance = index / 10 if kind == "complete_motion" else 0.0
        trace.append({"frame": frame, "time_s": time,
                      "position_m": [distance, 0, 0],
                      "position": {"x": distance, "y": 0, "z": 0},
                      "heading_deg": 0, "speed_mps": 2 if kind == "complete_motion" else 0,
                      "speed_mph": (2 / .44704) if kind == "complete_motion" else 0,
                      "velocity_mps": [2, 0, 0] if kind == "complete_motion" else [0, 0, 0],
                      "control": {}})
        mapping.append({"video_frame": index, "carla_frame": frame,
                        "native_frame": frame, "time_s": time})
    return trace, mapping


def base_result(case, construction):
    return {"case_id": case["case_id"], "measured_values": {},
            "target_checks": [{"target": "diagnostic_motion_only", "requested": 900,
                               "measured": 0, "method": "synthetic source-shaped CPU fixture",
                               "tolerance": 0, "matched": False,
                               "physical_cause_confirmed": False,
                               "cause_evidence": "no Native or legal acceptance"}],
            "setup_confirmed": False, "behavior_attempted": False,
            "maneuver_completed": False, "termination_reason": "CPU diagnostic only",
            "physical_failure_flags": {"native_unverified": True},
            "trace_reference": "trace.jsonl", "video_references": ["raw.mkv"],
            "video_frame_map_reference": "video_frames.jsonl",
            "recording_description": construction["recording_description"],
            "recording_evidence": [], "realized_observables": {},
            "physical_acceptance_claimed": False}


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    for case in PLAN["cases"]:
        suffix = case["case_id"].split("__")[-1]
        construction_path = ROOT / "cases" / suffix / "construction.json"
        construction = json.loads(construction_path.read_text())
        config = next(json.loads(item["content"]) for item in construction["files"]
                      if item["path"] == "config.json")
        fixtures = []
        for kind, status in (("complete_motion", "met"),
                             ("incomplete_motion", "not_met"),
                             ("missing_evidence", "unverified")):
            source = SCRATCH / suffix / kind
            source.mkdir(parents=True, exist_ok=True)
            write(source / "config.json", config)
            write(source / "acquisition-provenance.json",
                  {"provenance_kind": "synthetic_fixture", "diagnostic_fixture": True})
            trace, mapping = source_rows(kind)
            (source / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in mapping))
            if kind != "missing_evidence":
                (source / "trace.jsonl").write_text("".join(json.dumps(row) + "\n" for row in trace))
            result = physical_result(source, base_result(case, construction))
            if result["physical_checks"]["maneuver"]["status"] != status:
                raise ValueError("synthetic motion outcome differs: " + suffix + " " + kind)
            result_path = ROOT / ("physical-" + suffix + "-" + kind + ".json")
            write(result_path, result)
            log = ROOT / ("cpu-physical-" + suffix + "-" + kind + ".log")
            log.write_text("Synthetic source-shaped motion outcome: " + suffix + " " + kind +
                           "\nstatus=" + status + "\nsource_bound=True\n")
            fixtures.append({"kind": kind,
                             "command": "PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/" +
                                        ROOT.name + "/build_physical_outcomes.py",
                             "exit_code": 0, "log": log.name, "log_sha256": sha(log),
                             "result": result_path.name, "result_sha256": sha(result_path)})
        lifecycle_log = ROOT / ("cpu-physical-lifecycle-" + suffix + ".log")
        if not lifecycle_log.is_file() or EVENTS[-1] not in lifecycle_log.read_text():
            continue
        receipt = {"format": "worker-physical-preparation", "case_id": case["case_id"],
                   "construction_sha256": sha(construction_path), "fixtures": fixtures,
                   "lifecycle": {"events": EVENTS, "exit_code": 0,
                                 "log": lifecycle_log.name, "log_sha256": sha(lifecycle_log)},
                   "physical_acceptance_claimed": False}
        write(ROOT / ("physical-preparation-" + suffix + ".json"), receipt)


if __name__ == "__main__":
    main()
