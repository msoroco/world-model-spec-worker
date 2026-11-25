"""Synthetic motion outcomes for the saved physical completion criterion."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path[:0] = [str(REPO / "runtime"), str(REPO / "runtime/scenario_pipeline")]
from scenario_pipeline.worker_exchange.native_output import assess_physical


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def body(x):
    return [[x - .4, -.4], [x + .4, -.4], [x + .4, .4], [x - .4, .4]]


def run(case, kind, scratch, result):
    if kind not in ("complete_motion", "incomplete_motion", "missing_evidence"):
        raise ValueError("unsupported fixture kind")
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    entry = next(x for x in manifest["cases"] if x["case_id"] == case)
    construction = json.loads((ROOT / entry["construction"]).read_text())
    config = json.loads(next(x["content"] for x in construction["files"]
                             if x["path"] == "config.json"))
    scratch.mkdir(parents=True, exist_ok=False)
    (scratch / "config.json").write_text(json.dumps(config) + "\n")
    (scratch / "control_context.json").write_text(json.dumps({
        "intersection_polygon_xy_m": [[-2, -2], [2, -2], [2, 2], [-2, 2]]}) + "\n")
    with (scratch / "video_frames.jsonl").open("x") as mapping:
        for i in range(900):
            mapping.write(json.dumps({"video_frame": i, "carla_frame": i + 1,
                                      "time_s": i / 20}) + "\n")
    if kind != "missing_evidence":
        with (scratch / "trace.jsonl").open("x") as trace, \
                (scratch / "interaction_history.jsonl").open("x") as history:
            for i in range(900):
                x = -5 + (10 * i / 899 if kind == "complete_motion" else i / 899)
                trace.write(json.dumps({"frame": i + 1, "time_s": i / 20,
                                        "position_m": [x, 0]}) + "\n")
                history.write(json.dumps({"frame": i + 1, "time_s": i / 20,
                                          "ego": {"body_vertices_m": body(x)}}) + "\n")
    assessed = assess_physical(scratch, config, [])
    output = {"case_id": case, "fixture_kind": kind,
              "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
              "construction_sha256": sha(ROOT / entry["construction"]),
              "physical_checks": assessed["physical_checks"],
              "realized_observables": assessed["realized_observables"],
              "maneuver_completed": assessed["maneuver_completed"],
              "legal_verdict_claimed": False, "native_acceptance_claimed": False}
    result.write_text(json.dumps(output, sort_keys=True) + "\n")
    expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                "missing_evidence": "unverified"}[kind]
    status = assessed["physical_checks"]["maneuver"]["status"]
    if status != expected:
        raise ValueError(f"{kind} returned {status}, expected {expected}")
    print(json.dumps({"case_id": case, "kind": kind, "status": status}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    run(args.case, args.kind, args.scratch, args.result)
