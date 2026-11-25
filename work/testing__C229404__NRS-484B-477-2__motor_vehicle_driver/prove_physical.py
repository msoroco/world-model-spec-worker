"""Exercise three source-bound parking outcomes and capture closure ordering.

These are synthetic CPU fixtures. They do not claim a Native parking result.
"""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

from physical_parking import assess


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(root, position, outcome):
    source = root / "original-attempt"
    source.mkdir(parents=True)
    write(source / "inventory.json", {"diagnostic_fixture": True, "provenance_kind": "synthetic_fixture"})
    frames = [{"frame": 100 + i, "time_s": i / 20} for i in range(9)]
    write(source / "frame_map.json", {"frames": frames})
    states = ["approaching", "stopping", "parked", "parked", "parked",
              "parked", "departing", "departing", "departing"]
    if outcome == "incomplete_motion":
        states[-3:] = ["parked"] * 3
    write(source / "activity.json", {"samples": [dict(row, state=states[i],
        speed_mps=0 if states[i] == "parked" else 1) for i, row in enumerate(frames)]})
    write(source / "vehicle_footprint.json", {"samples": [dict(row,
        polygon_m=[[i, 0], [i + 1, 0], [i + 1, 1], [i, 1]])
        for i, row in enumerate(frames)]})
    (root / "trace.jsonl").write_text("".join(json.dumps(row) + "\n" for row in frames))
    (root / "video_frames.jsonl").write_text("".join(json.dumps(dict(row,
        carla_frame=row["frame"], video_frame=i)) + "\n" for i, row in enumerate(frames)))
    if outcome == "missing_evidence":
        (source / "activity.json").unlink()
    config = {"parking_position": position}
    measured = {"max_access_intrusion_area_m2": 0 if position == "clear" else 2.0}
    return assess(root, config, measured)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--position", choices=("clear", "overlap"), required=True)
    parser.add_argument("--construction", required=True)
    parser.add_argument("--scratch", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    scratch = Path(args.scratch).resolve()
    if not args.case.startswith(output.name + "__") or ".runtime-work" not in scratch.parts:
        raise ValueError("Exact case and ignored scratch are required")
    scratch.mkdir(parents=True, exist_ok=True)
    fixtures = []
    for kind, expected in (("complete_motion", "met"), ("incomplete_motion", "not_met"),
                           ("missing_evidence", "unverified")):
        root = scratch / kind
        if root.exists():
            shutil.rmtree(root)
        root.mkdir()
        result = fixture(root, args.position, kind)
        if result["physical_checks"]["maneuver"]["status"] != expected:
            raise ValueError("Physical outcome differs: " + kind)
        result.update(provenance_kind="synthetic_fixture", diagnostic_fixture=True,
                      case_id=args.case, fixture_kind=kind)
        result_path = output / ("physical-" + args.case.rsplit("__", 1)[-1] + "-" + kind + ".json")
        log_path = output / ("physical-" + args.case.rsplit("__", 1)[-1] + "-" + kind + ".log")
        write(result_path, result)
        log_path.write_text("PASS " + args.case + " " + kind + " " + expected + "\n")
        fixtures.append({"kind": kind, "command": "python prove_physical.py --case " + args.case,
                         "exit_code": 0, "log": log_path.name, "log_sha256": sha(log_path),
                         "result": result_path.name, "result_sha256": sha(result_path)})
    if not __import__("os").environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "").endswith("c229404-physical-runtime"):
        raise ValueError("Export ignored runtime output root before lifecycle proof")
    repo = output.parent.parent
    sys.path.insert(0, str(repo / "runtime/scenario_pipeline"))
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release
    life_root = scratch / "lifecycle"
    if life_root.exists():
        shutil.rmtree(life_root)
    life_root.mkdir()
    (life_root / "construction.json").write_bytes(Path(args.construction).read_bytes())
    (life_root / "runner.py").write_text("# synthetic lifecycle proof\n")
    (life_root / "trace.jsonl").write_text('{"frame": 100}\n')
    (life_root / "video_frames.jsonl").write_text('{"video_frame": 0, "carla_frame": 100}\n')
    (life_root / "acquisition-provenance.json").write_text('{"diagnostic_fixture": true}\n')
    seal = seal_capture(life_root, frames=1, restoration={"restored": True}, errors=[],
                        encoder_exit_codes={"overview": 0}, context={"synthetic_fixture": True})
    exit_receipt = record_native_exit(life_root)
    owner = acknowledge_owner_release(life_root, life_root / "owner-release.json", True)
    if exit_receipt["capture_seal_sha256"] != sha(life_root / "capture-seal.json") or owner["native_exit_sha256"] != sha(life_root / "native-exit.json"):
        raise ValueError("Lifecycle receipt binding failed")
    events = seal["events"] + [exit_receipt["event"], owner["event"], "saved_processing_started"]
    lifecycle = output / ("physical-" + args.case.rsplit("__", 1)[-1] + "-lifecycle.log")
    lifecycle.write_text("\n".join(events) + "\n")
    receipt = {"format": "worker-physical-preparation", "case_id": args.case,
               "construction_sha256": sha(Path(args.construction)), "fixtures": fixtures,
               "lifecycle": {"events": events, "exit_code": 0, "log": lifecycle.name,
                             "log_sha256": sha(lifecycle)}}
    path = output / ("physical-" + args.case.rsplit("__", 1)[-1] + "-receipt.json")
    write(path, receipt)
    print(path)


if __name__ == "__main__":
    main()
