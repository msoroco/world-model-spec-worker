"""Run the exported physical checker on deterministic synthetic travel sources."""

import argparse
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from scenario_pipeline.worker_exchange.native_output import assess_physical


def config_for(case_id):
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    entry = next((item for item in manifest["cases"] if item["case_id"] == case_id), None)
    if entry is None:
        raise ValueError("Unknown exact case")
    construction = json.loads((HERE / entry["construction"]).read_text())
    return json.loads(next(item["content"] for item in construction["files"]
                           if item["path"] == "config.json"))


def run(case_id, kind):
    if kind not in ("complete_motion", "incomplete_motion", "missing_evidence"):
        raise ValueError("Unknown fixture kind")
    config = config_for(case_id)
    count = round(float(config["duration_s"]) * float(config["rate_hz"]))
    if count < 2:
        raise ValueError("Invalid planned frame count")
    with TemporaryDirectory(prefix="c111273-physical-", dir=ROOT / ".runtime-work") as temp:
        base = Path(temp)
        (base / "config.json").write_text(json.dumps(config, sort_keys=True) + "\n")
        frames = []
        trace = []
        for index in range(count):
            frame = 1000 + index
            time_s = index / float(config["rate_hz"])
            progress = (24.0 if kind == "complete_motion" else 5.0) * index / (count - 1)
            frames.append({"carla_frame": frame, "time_s": time_s})
            trace.append({"frame": frame, "time_s": time_s, "position_m": [progress, 0.0]})
        (base / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in frames))
        if kind != "missing_evidence":
            (base / "trace.jsonl").write_text("".join(json.dumps(row) + "\n" for row in trace))
        assessed = assess_physical(base, config)
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[kind]
        if assessed["physical_checks"]["maneuver"]["status"] != expected:
            raise ValueError("Checker rejected the authored synthetic outcome")
        return {"case_id": case_id, "fixture_kind": kind,
                "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
                "actual_native_capture": False, "physical_acceptance_claimed": False,
                "legal_acceptance_claimed": False, **assessed}


def lifecycle():
    ordered = ["capture_finished", "encoders_closed", "restoration_verified",
               "native_exit", "owner_released", "saved_processing_started"]
    def valid(events):
        return (events.index("capture_finished") < events.index("encoders_closed")
                < events.index("restoration_verified") < events.index("native_exit")
                < events.index("owner_released") < events.index("saved_processing_started"))
    premature = ordered.copy()
    premature[3], premature[4] = premature[4], premature[3]
    if not valid(ordered) or valid(premature):
        raise AssertionError("Early release was not rejected")
    return ordered


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case")
    parser.add_argument("--kind", required=True,
                        choices=("complete_motion", "incomplete_motion", "missing_evidence", "lifecycle"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.kind == "lifecycle":
        result = {"events": lifecycle(), "provenance_kind": "synthetic_fixture"}
    else:
        if not args.case:
            raise ValueError("Exact case required")
        result = run(args.case, args.kind)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(args.case or "lifecycle", args.kind, "synthetic_fixture", "passed")
