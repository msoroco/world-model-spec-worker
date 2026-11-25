"""Diagnostic physical outcomes and Native ownership ordering for 250-2."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1] / "runtime"))
from scenario_pipeline.worker_exchange.native_output import physical_result, seal_capture
from scenario_pipeline.worker_exchange.saved_processing import (
    record_native_exit, acknowledge_owner_release, copy_sources)


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.case not in {ROOT.name + "__" + name for name in (
            "timing_below_training", "timing_inside_training",
            "timing_above_training", "right_approach_inside")}:
        raise ValueError("foreign median-opening case")
    config = json.loads((args.attempt / "config.json").read_text())
    if config["selected_case_id"] != args.case:
        raise ValueError("diagnostic source selects another case")
    args.output.mkdir(parents=True, exist_ok=False)
    outcomes = (("complete_motion", "met"), ("incomplete_motion", "not_met"),
                ("missing_evidence", "unverified"))
    for kind, expected in outcomes:
        folder = args.output / kind
        shutil.copytree(args.attempt, folder)
        source = folder / "crossing_history.jsonl"
        if kind != "missing_evidence":
            rows = [json.loads(line) for line in source.read_text().splitlines()]
            if kind == "complete_motion":
                axis = config["physical_completion"]["exit_axis"]
                for row in rows[-2:]:
                    for vertex in row["ego_vertices_m"]:
                        vertex[axis] = 6.0
            else:
                first = rows[0]["ego_vertices_m"]
                for row in rows:
                    row["ego_vertices_m"] = first
            source.write_text("".join(json.dumps(row) + "\n" for row in rows))
        else:
            source.unlink()
        result = physical_result(folder, {"case_id": args.case, "target_checks": []})
        if result["physical_checks"]["maneuver"]["status"] != expected:
            raise ValueError("physical diagnostic outcome mismatch: " + kind)
        write(args.output / (kind + ".json"), result)
        print(kind, expected)
    complete = args.output / "complete_motion"
    seal = seal_capture(complete, frames=9,
                        restoration={"restored": True,
                                     "settings_readback": "CPU diagnostic protocol"},
                        errors=[], encoder_exit_codes={"diagnostic": 0})
    record_native_exit(complete)
    acknowledge_owner_release(complete, complete / "owner-release.json", True)
    stage = args.output / "saved_stage"
    stage.mkdir()
    copy_sources(complete, stage)
    print("lifecycle", *seal["events"], "native_exit", "owner_released",
          "saved_processing_started")


if __name__ == "__main__":
    main()
