"""Exercise the pinned physical checker with deterministic synthetic turn sources."""

import argparse
import json
import math
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from scenario_pipeline.worker_exchange.native_output import assess_physical


def _config(case_id):
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    entry = next((e for e in manifest["cases"] if e["case_id"] == case_id), None)
    if entry is None:
        raise ValueError("Unknown exact case")
    construction = json.loads((HERE / entry["construction"]).read_text())
    return json.loads(next(f["content"] for f in construction["files"] if f["path"] == "config.json"))


def _write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def run(case_id, kind):
    if kind not in ("complete_motion", "incomplete_motion", "missing_evidence"):
        raise ValueError("Unknown fixture outcome")
    config = _config(case_id)
    count = round(float(config["duration_s"]) * float(config["rate_hz"]))
    if count < 2:
        raise ValueError("Invalid configured capture length")
    with TemporaryDirectory(prefix="c152976-physical-", dir=ROOT / ".runtime-work") as temp:
        base = Path(temp)
        (base / "config.json").write_text(json.dumps(config, sort_keys=True) + "\n")
        frames = []
        motion = []
        trace = []
        for index in range(count):
            fraction = index / (count - 1)
            frame = 1000 + index
            time_s = index / float(config["rate_hz"])
            angle = fraction * math.pi / 2
            center_x = 10 * math.sin(angle)
            center_y = 10 * (1 - math.cos(angle))
            heading = 0.0 if kind == "incomplete_motion" else 90 * fraction
            body = [[center_x - 0.5, center_y - 0.5], [center_x + 0.5, center_y - 0.5],
                    [center_x + 0.5, center_y + 0.5], [center_x - 0.5, center_y + 0.5]]
            frames.append({"carla_frame": frame, "time_s": time_s})
            trace.append({"frame": frame, "heading_deg": heading})
            motion.append({"frame": frame, "time_s": time_s,
                           "body_vertices_m": body, "heading_deg": heading})
        _write_rows(base / "video_frames.jsonl", frames)
        _write_rows(base / "trace.jsonl", trace)
        if kind != "missing_evidence":
            _write_rows(base / "native/turn_motion.jsonl", motion)
        assessed = assess_physical(base, config)
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[kind]
        actual = assessed["physical_checks"]["maneuver"]["status"]
        if actual != expected:
            raise ValueError(f"Physical fixture expected {expected}, observed {actual}")
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
    premature = list(events)
    premature[3], premature[4] = premature[4], premature[3]
    if not valid(events) or valid(premature):
        raise AssertionError("Lifecycle checker failed to reject early owner release")
    return events


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case")
    parser.add_argument("--kind", required=True,
                        choices=("complete_motion", "incomplete_motion", "missing_evidence", "lifecycle"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.kind == "lifecycle":
        value = {"events": lifecycle(), "provenance_kind": "synthetic_fixture"}
    else:
        if not args.case:
            raise ValueError("Exact case required")
        value = run(args.case, args.kind)
    Path(args.output).write_text(json.dumps(value, indent=2) + "\n")
    print(args.case or "lifecycle", args.kind, "synthetic_fixture", "passed")
