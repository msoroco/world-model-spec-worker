"""Test the selected body-clearance checker with three synthetic outcomes."""

import argparse
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange.native_output import physical_result


CASES = ("officer_controls_go", "officer_controls_hold", "officer_present_inactive")
EXPECTED = {"complete_motion": "met", "incomplete_motion": "not_met",
            "missing_evidence": "unverified"}


def body(x, y=0):
    return [[x - 1, y - 1], [x - 1, y + 1], [x + 1, y + 1], [x + 1, y - 1]]


def run(suffix, kind, output):
    if suffix not in CASES or kind not in EXPECTED:
        raise ValueError("Unknown selected physical fixture")
    case_id = HERE.name + "__" + suffix
    manifest = json.loads((HERE / "execution-manifest-draft.json").read_text())
    entry = next(item for item in manifest["cases"] if item["case_id"] == case_id)
    construction = json.loads((HERE / entry["construction"]).read_text())
    config = json.loads(next(item["content"] for item in construction["files"]
                             if item["path"] == "config.json"))
    import tempfile
    with tempfile.TemporaryDirectory(prefix="c157964-sub2-physical-") as directory:
        root = Path(directory)
        (root / "config.json").write_text(json.dumps(config) + "\n")
        (root / "officer_context.json").write_text(json.dumps({
            "intersection_polygon_xy_m": [[-5, -5], [5, -5], [5, 5], [-5, 5]]}) + "\n")
        (root / "acquisition-provenance.json").write_text(json.dumps({
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
            "physical_acceptance_claimed": False}) + "\n")
        rows = []
        frames = []
        trace = []
        for index, x in enumerate((-15, 0, 12, 16)):
            subject_x = -15 if kind == "incomplete_motion" else x
            rows.append({"frame": 100 + index, "time_s": 5 + index / 20,
                         "ego": {"body_vertices_xy_m": body(subject_x)},
                         "other_body_vertices_xy_m": body(subject_x, subject_x)})
            frames.append({"video_frame": index, "carla_frame": 100 + index,
                           "time_s": 5 + index / 20})
            trace.append({"frame": 100 + index, "time_s": 5 + index / 20,
                          "position_m": [subject_x, 0, 0], "speed_mps": 1.0})
        (root / "officer_history.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        (root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in frames))
        (root / "trace.jsonl").write_text("".join(json.dumps(row) + "\n" for row in trace))
        if kind == "missing_evidence":
            (root / "officer_history.jsonl").unlink()
        result = physical_result(root, {"target_checks": [], "realized_observables": {},
                                        "setup_confirmed": False, "behavior_attempted": False,
                                        "maneuver_completed": False})
        status = result["physical_checks"]["maneuver"]["status"]
        if (status != EXPECTED[kind] or result["maneuver_completed"] != (status == "met")
                or result.get("provenance_kind") != "synthetic_fixture"
                or result.get("diagnostic_fixture") is not True
                or result.get("physical_acceptance_claimed") is not False):
            raise ValueError("Selected physical outcome proof differs")
        if kind == "complete_motion" and not result["realized_observables"]:
            raise ValueError("Complete source motion has no measurements")
        output = Path(output)
        output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
        print(json.dumps({"case_id": case_id, "kind": kind, "status": status}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=CASES, required=True)
    parser.add_argument("--kind", choices=sorted(EXPECTED), required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.case, args.kind, args.output)
