"""Exercise the common station-turn checker with synthetic original-shaped sources."""

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


def common_config(case_id):
    entries = json.loads((HERE / "execution-manifest.json").read_text())["cases"]
    configs = []
    for entry in entries:
        construction = json.loads((HERE / entry["construction"]).read_text())
        configs.append(json.loads(next(f["content"] for f in construction["files"]
                                       if f["path"] == "config.json")))
    matching = [(entry["case_id"], cfg) for entry, cfg in zip(entries, configs) if entry["case_id"] == case_id]
    if len(matching) != 1:
        raise ValueError("Select one exact case")
    return matching[0]


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def run(case_id, kind):
    if kind not in ("complete_motion", "incomplete_motion", "missing_evidence"):
        raise ValueError("Unknown fixture kind")
    selected_case, config = common_config(case_id)
    count = round(float(config["duration_s"]) * float(config["rate_hz"]))
    with TemporaryDirectory(prefix="c111706-physical-", dir=ROOT / ".runtime-work") as temp:
        base = Path(temp)
        (base / "config.json").write_text(json.dumps(config, sort_keys=True) + "\n")
        (base / "station_survey.json").write_text(json.dumps({"kind": "synthetic_station_context"}) + "\n")
        mapping = []
        trace = []
        motion = []
        for index in range(count):
            fraction = index / (count - 1)
            angle = math.pi * fraction
            x, y = 10 * math.sin(angle), 10 * (1 - math.cos(angle))
            heading = 0.0 if kind == "incomplete_motion" else 180 * fraction
            frame = 1000 + index
            time_s = index / float(config["rate_hz"])
            body = [[x - 0.5, y - 0.5], [x + 0.5, y - 0.5],
                    [x + 0.5, y + 0.5], [x - 0.5, y + 0.5]]
            mapping.append({"carla_frame": frame, "time_s": time_s})
            trace.append({"frame": frame, "heading_deg": heading})
            motion.append({"frame": frame, "time_s": time_s,
                           "body_corners_xy": body, "heading_deg": heading})
        write_rows(base / "video_frames.jsonl", mapping)
        write_rows(base / "trace.jsonl", trace)
        if kind != "missing_evidence":
            write_rows(base / "subject_original.jsonl", motion)
        assessed = assess_physical(base, config)
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[kind]
        if assessed["physical_checks"]["maneuver"]["status"] != expected:
            raise ValueError("Synthetic fixture did not produce the expected checker result")
        return {"case_id": selected_case, "fixture_kind": kind,
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
    early = ordered.copy()
    early[3], early[4] = early[4], early[3]
    if not valid(ordered) or valid(early):
        raise AssertionError("Early owner release was not rejected")
    return {"events": ordered, "provenance_kind": "synthetic_fixture"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", required=True,
                        choices=("complete_motion", "incomplete_motion", "missing_evidence", "lifecycle"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = lifecycle() if args.kind == "lifecycle" else run(args.case, args.kind)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(args.kind, "synthetic_fixture", "passed")
