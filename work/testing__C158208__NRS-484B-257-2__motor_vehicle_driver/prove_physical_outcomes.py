"""Exercise exact-case physical classifications on synthetic original-tick sources."""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
OUTPUT_ROOT = ROOT / ".runtime-work"
requested = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")).resolve()
if not requested.is_relative_to(OUTPUT_ROOT.resolve()):
    raise ValueError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
sys.dont_write_bytecode = True
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
from yield_capture import CAMERAS, EntrySourceWriter
from worker_exchange.native_output import physical_result, seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release


class Body:
    def __init__(self, actor_id, x):
        self.id, self.x = actor_id, x
        self.bounding_box = NS(get_world_vertices=self.vertices)

    def vertices(self, _transform):
        return [NS(x=self.x + dx, y=dy, z=z)
                for dx, dy in ((-1, -1), (-1, 1), (1, 1), (1, -1))
                for z in (0, 1)]

    def get_transform(self):
        return None

    def get_velocity(self):
        return NS(x=3.0, y=0.0, z=0.0)


def make_case(case, root, positions):
    manifest = json.loads((PACKAGE / "execution-manifest.json").read_text())
    entry = next(e for e in manifest["cases"] if e["case_id"] == case)
    construction = json.loads((PACKAGE / entry["construction"]).read_text())
    config = json.loads(next(f["content"] for f in construction["files"]
                             if f["path"] == "config.json"))
    (root / "config.json").write_text(json.dumps(config) + "\n")
    (root / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}) + "\n")
    context = {"case_id": case, "native_yield_sign_id": 25,
               "ego_entrance_device": "yield", "non_through_highway": True,
               "ego_approach_road_id": 158208,
               "intersection_polygon_xy_m": [[10, -5], [20, -5], [20, 5], [10, 5]]}
    review = {"marked_stop_line_observed": True, "near_crosswalk_observed": False,
              "reference_boundary": {"source": "marked_stop_line",
                                     "origin_xy_m": [10, 0], "ego_forward_xy": [1, 0]}}
    ego, other = Body(101, 0), Body(102, 12)
    writer = EntrySourceWriter(root, context, review, ego, other, NS(id=25))
    snapshot = NS(frame=100)
    world = NS(get_snapshot=lambda: snapshot)
    with (root / "trace.jsonl").open("w") as trace:
        for offset, x in enumerate(positions):
            frame = 100 + offset
            snapshot.frame, ego.x = frame, x
            time_s = frame / 20
            writer.add(world, frame, time_s, {name: frame for name in CAMERAS})
            trace.write(json.dumps({"frame": frame, "time_s": time_s,
                                    "position_m": [x, 0, 0]}) + "\n")
    return config


def lifecycle(case, root):
    make_case(case, root, (0, 12, 25))
    manifest = json.loads((PACKAGE / "execution-manifest.json").read_text())
    entry = next(e for e in manifest["cases"] if e["case_id"] == case)
    construction = json.loads((PACKAGE / entry["construction"]).read_text())
    (root / "construction.json").write_text(json.dumps(construction) + "\n")
    (root / "runner.py").write_text(next(f["content"] for f in construction["files"]
                                         if f["path"] == "runner.py"))
    try:
        seal_capture(root, frames=3, restoration={"restored": True}, errors=[],
                     encoder_exit_codes={"fixture_encoder": 1})
    except ValueError as error:
        if "unclosed/failed encoders" not in str(error):
            raise
    else:
        raise ValueError("Failed encoder sealed")
    seal = seal_capture(root, frames=3, restoration={"restored": True}, errors=[],
                        encoder_exit_codes={"fixture_encoder": 0})
    try:
        acknowledge_owner_release(root, root / "owner-release.json", True)
    except ValueError as error:
        if "Native process has not exited" not in str(error):
            raise
    else:
        raise ValueError("Premature release passed")
    native = record_native_exit(root)
    owner = acknowledge_owner_release(root, root / "owner-release.json", True)
    saved = json.loads((PACKAGE / "selected-post-capture.log").read_text())
    rows = [r for r in saved["cases"] if r["case_id"] == case]
    if len(rows) != 1 or rows[0]["positive_saved_processing"] is not True:
        raise ValueError("Exact selected saved-processing CPU proof absent")
    events = seal["events"] + [native["event"], owner["event"],
                               "saved_processing_started"]
    expected = ["capture_finished", "encoders_closed", "restoration_verified",
                "native_exit", "owner_released", "saved_processing_started"]
    if events != expected:
        raise ValueError("Lifecycle event order differs")
    return {"case_id": case, "events": events, "failed_encoder_rejected": True,
            "premature_release_rejected": True, "diagnostic_fixture": True,
            "physical_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", required=True,
                        choices=("complete_motion", "incomplete_motion", "missing_evidence",
                                 "lifecycle"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.case not in {e["case_id"] for e in
                         json.loads((PACKAGE / "execution-manifest.json").read_text())["cases"]}:
        raise ValueError("Unknown exact case")
    OUTPUT_ROOT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=OUTPUT_ROOT, prefix="c158208-physical-outcome-") as name:
        root = Path(name)
        if args.kind == "lifecycle":
            result = lifecycle(args.case, root)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
            print(json.dumps(result, sort_keys=True))
            return
        positions = (0, 12, 25) if args.kind == "complete_motion" else (0, 12, 12)
        make_case(args.case, root, positions)
        if args.kind == "missing_evidence":
            (root / "interaction_history.jsonl").unlink()
        result = physical_result(root, {"target_checks": [{"matched": True}]})
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}[args.kind]
        if (result["physical_checks"]["maneuver"]["status"] != expected
                or result["maneuver_completed"] != (expected == "met")
                or result["provenance_kind"] != "synthetic_fixture"
                or result["diagnostic_fixture"] is not True
                or result["physical_acceptance_claimed"] is not False):
            raise ValueError("Physical outcome differs: " + args.kind)
        if expected == "met" and not result["realized_observables"]:
            raise ValueError("Complete fixture lacks measured observations")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"case_id": args.case, "fixture": args.kind,
                          "maneuver_status": expected, "setup_status":
                          result["physical_checks"]["setup"]["status"],
                          "diagnostic_fixture": True}, sort_keys=True))


if __name__ == "__main__":
    main()
