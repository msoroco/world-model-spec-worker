"""CPU-only source fixtures for the current runtime reverse-goal assessor."""

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / "runtime" / "scenario_pipeline"))


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def rows(path, values):
    path.write_text("".join(json.dumps(value, sort_keys=True) + "\n" for value in values))


def prove(case_id, outcome):
    from worker_exchange.native_output import physical_result

    key = case_id.split("__")[-1]
    if key not in ("reverse_clear", "reverse_tangent", "reverse_overlap"):
        raise ValueError("exact C215286 case required")
    if outcome not in ("complete_motion", "incomplete_motion", "missing_evidence"):
        raise ValueError("unknown physical fixture")
    scratch = REPO / ".runtime-work"
    with tempfile.TemporaryDirectory(dir=scratch, prefix="c215286-physical-") as temporary:
        stage = Path(temporary)
        config = {"law_id": "NRS-484B-113-2", "cell_id": "C215286",
                  "actor": "motor_vehicle_driver", "selected_case_id": case_id,
                  "duration_s": 45, "rate_hz": 20,
                  "motion_route_xy_m": [[100.0, 1.75], [98.0, 1.75]],
                  "physical_completion": {"goal_tolerance_m": .25,
                                          "minimum_progress_m": .25}}
        write(stage / "config.json", config)
        write(stage / "acquisition-provenance.json",
              {"provenance_kind": "synthetic_fixture", "diagnostic_fixture": True})
        mapping = []
        trace = []
        reverse = []
        for index in range(900):
            t = index / 20
            progress = index / 899
            x = 100 - (1.0 if outcome == "incomplete_motion" else 2.0) * progress
            body = [[x - 1, .75, 0], [x + 1, .75, 0],
                    [x + 1, 2.75, 0], [x - 1, 2.75, 0]]
            frame = 40000 + index
            mapping.append({"video_frame": index, "carla_frame": frame,
                            "native_frame": frame, "time_s": t})
            trace.append({"frame": frame, "time_s": t,
                          "position_m": [x, 1.75, 0], "heading_deg": 0.0,
                          "velocity_mps": [-1.0, 0.0, 0.0]})
            reverse.append({"frame": frame, "time_s": t,
                            "body_vertices_m": body, "heading_deg": 0.0,
                            "velocity_mps": [-1.0, 0.0, 0.0]})
        rows(stage / "video_frames.jsonl", mapping)
        rows(stage / "trace.jsonl", trace)
        if outcome != "missing_evidence":
            rows(stage / "reverse_history.jsonl", reverse)
        write(stage / "crosswalk_context.json",
              {"crosswalk_source": "synthetic CPU physical diagnostic",
               "crosswalk_polygon_xy": [[101, 0], [103, 0], [103, 4], [101, 4]]})
        result = physical_result(stage, {"target_checks": [{"target": "fixture source",
                                                            "matched": True}]})
        status = result["physical_checks"]["maneuver"]["status"]
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[outcome]
        if status != expected or result["maneuver_completed"] != (expected == "met"):
            raise ValueError("physical outcome did not match original-frame fixture")
        return {"format": "c215286-cpu-physical-fixture", "case_id": case_id,
                "outcome": outcome, "physical_checks": result["physical_checks"],
                "maneuver_completed": result["maneuver_completed"],
                "realized_observables": result["realized_observables"],
                "provenance_kind": result["provenance_kind"],
                "diagnostic_fixture": result["diagnostic_fixture"],
                "physical_acceptance_claimed": False,
                "legal_acceptance_claimed": False}


def lifecycle(case_id):
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, _closure

    scratch = REPO / ".runtime-work"
    with tempfile.TemporaryDirectory(dir=scratch, prefix="c215286-lifecycle-") as temporary:
        stage = Path(temporary)
        (stage / "runner.py").write_text("# synthetic lifecycle fixture\n")
        write(stage / "construction.json", {"case_id": case_id})
        write(stage / "acquisition-provenance.json",
              {"provenance_kind": "synthetic_fixture", "diagnostic_fixture": True})
        rows(stage / "trace.jsonl", [{"frame": 1, "time_s": 0.0}])
        rows(stage / "video_frames.jsonl",
             [{"video_frame": 0, "carla_frame": 1, "time_s": 0.0}])
        for bad in ({"restored": False},):
            try:
                seal_capture(stage, frames=1, restoration=bad, errors=[],
                             encoder_exit_codes={"overview": 0})
            except ValueError:
                pass
            else:
                raise ValueError("unrestored capture was sealed")
        seal = seal_capture(stage, frames=1, restoration={"restored": True},
                            errors=[], encoder_exit_codes={"overview": 0})
        exit_record = record_native_exit(stage)
        owner_path = stage / "owner-release.json"
        acknowledge_owner_release(stage, owner_path, True)
        _closure(stage, owner_path, "synthetic_fixture", True)
        return {"case_id": case_id, "events": seal["events"] +
                [exit_record["event"], "owner_released", "saved_processing_started"],
                "synthetic_fixture": True, "native_resources_used": False,
                "passed": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--outcome", choices=("complete_motion", "incomplete_motion",
                                              "missing_evidence", "lifecycle"), required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    os.environ.setdefault("SCENARIO_PIPELINE_OUTPUT_ROOT",
                          str(REPO / ".runtime-work" / "c215286-physical-runtime"))
    result = lifecycle(args.case) if args.outcome == "lifecycle" else prove(args.case, args.outcome)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"case_id": args.case, "outcome": args.outcome,
                      "passed": True}))


if __name__ == "__main__":
    main()
