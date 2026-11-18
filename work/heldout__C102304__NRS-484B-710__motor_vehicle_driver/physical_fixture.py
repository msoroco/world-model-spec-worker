"""Exercise source-bound completion checks with declared synthetic motion rows."""

import argparse
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from scenario_pipeline.worker_exchange.native_output import assess_physical, default_descriptor


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def config_for(case_id):
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    entry = next((case for case in manifest["cases"] if case["case_id"] == case_id), None)
    if entry is None:
        raise ValueError("Unknown exact case")
    construction = json.loads((HERE / entry["construction"]).read_text())
    return json.loads(next(f["content"] for f in construction["files"] if f["path"] == "config.json"))


def run(case_id, kind):
    cfg = config_for(case_id)
    descriptor = default_descriptor(cfg)
    if descriptor["criterion"] != "travel_progress":
        raise ValueError("Fixture must be revised for the authored completion criterion")
    count = round(float(cfg["duration_s"]) * float(cfg["rate_hz"]))
    if count < 2:
        raise ValueError("Invalid configured capture length")
    with TemporaryDirectory(prefix="c374648-physical-", dir=ROOT / ".runtime-work") as temp:
        base = Path(temp)
        (base / "config.json").write_text(json.dumps(cfg, sort_keys=True) + "\n")
        frames, trace = [], []
        distance = descriptor["minimum_progress_m"] * (1.5 if kind == "complete_motion" else 0.1)
        for index in range(count):
            frame = 1000 + index
            time_s = index / float(cfg["rate_hz"])
            frames.append({"carla_frame": frame, "time_s": time_s})
            trace.append({"frame": frame, "time_s": time_s,
                          "position_m": [distance * index / (count - 1), 0.0]})
        write_rows(base / "video_frames.jsonl", frames)
        if kind != "missing_evidence":
            write_rows(base / "trace.jsonl", trace)
        assessed = assess_physical(base, cfg)
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[kind]
        observed = assessed["physical_checks"]["maneuver"]["status"]
        if observed != expected:
            raise AssertionError(f"Expected {expected}, got {observed}")
        return {"case_id": case_id, "fixture_kind": kind,
                "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
                "actual_native_capture": False, "physical_acceptance_claimed": False,
                "legal_acceptance_claimed": False, **assessed}


def lifecycle():
    events = ["capture_finished", "encoders_closed", "restoration_verified",
              "native_exit", "owner_released", "saved_processing_started"]
    def valid(sequence):
        return (sequence.index("capture_finished") < sequence.index("encoders_closed")
                < sequence.index("restoration_verified") < sequence.index("native_exit")
                < sequence.index("owner_released") < sequence.index("saved_processing_started"))
    early = list(events)
    early[3], early[4] = early[4], early[3]
    if not valid(events) or valid(early):
        raise AssertionError("Lifecycle ordering check failed")
    return events


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case")
    parser.add_argument("--kind", required=True,
                        choices=("complete_motion", "incomplete_motion", "missing_evidence", "lifecycle"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    value = {"events": lifecycle(), "provenance_kind": "synthetic_fixture"} if args.kind == "lifecycle" else run(args.case, args.kind)
    Path(args.output).write_text(json.dumps(value, indent=2) + "\n")
    print(args.case or "lifecycle", args.kind, "synthetic_fixture", "passed")
