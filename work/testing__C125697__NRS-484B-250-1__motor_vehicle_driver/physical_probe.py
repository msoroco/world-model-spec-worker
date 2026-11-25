"""Diagnostic-only proof of median crossing outcomes and ownership ordering."""
import argparse
import json
import shutil
from pathlib import Path

from worker_exchange.native_output import physical_result, seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, copy_sources


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.case not in ("testing__C125697__NRS-484B-250-1__motor_vehicle_driver__precedence",
                         "testing__C125697__NRS-484B-250-1__motor_vehicle_driver__advance"):
        raise ValueError("foreign median-opening case")
    if json.loads((args.attempt / "config.json").read_text())["selected_case_id"] != args.case:
        raise ValueError("diagnostic source selects another case")
    args.output.mkdir(parents=True, exist_ok=False)
    outcomes = (("complete_motion", "met"), ("incomplete_motion", "not_met"),
                ("missing_evidence", "unverified"))
    for kind, expected in outcomes:
        folder = args.output / kind
        shutil.copytree(args.attempt, folder)
        if kind == "incomplete_motion":
            source = folder / "crossing_history.jsonl"
            rows = [json.loads(line) for line in source.read_text().splitlines()]
            first = rows[0]["ego_vertices_m"]
            for row in rows:
                row["ego_vertices_m"] = first
            source.write_text("".join(json.dumps(row) + "\n" for row in rows))
        elif kind == "missing_evidence":
            (folder / "crossing_history.jsonl").unlink()
        result = physical_result(folder, {"case_id": args.case, "target_checks": []})
        if result["physical_checks"]["maneuver"]["status"] != expected:
            raise ValueError("physical diagnostic outcome mismatch: " + kind)
        write(args.output / (kind + ".json"), result)
        print(kind, expected)
    complete = args.output / "complete_motion"
    seal = seal_capture(complete, frames=9,
                        restoration={"restored": True, "settings_readback": "CPU diagnostic protocol"},
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
