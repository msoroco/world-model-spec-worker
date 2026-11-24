"""Exercise current-runtime intersection completion on the own source writer."""

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
if requested == Path.cwd() or not requested.is_relative_to(OUTPUT_ROOT.resolve()):
    raise ValueError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")
sys.dont_write_bytecode = True
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
from yield_capture import CAMERAS, EntrySourceWriter
from worker_exchange.native_output import physical_result


class Body:
    def __init__(self, actor_id, x):
        self.id = actor_id
        self.x = x
        self.bounding_box = NS(get_world_vertices=self.vertices)

    def vertices(self, _transform):
        return [NS(x=self.x + dx, y=dy, z=z)
                for dx, dy in ((-1, -1), (-1, 1), (1, 1), (1, -1)) for z in (0, 1)]

    def get_transform(self):
        return None

    def get_velocity(self):
        return NS(x=3.0, y=0.0, z=0.0)


def main():
    config = json.loads((PACKAGE / "config.json").read_text())
    context = {"case_id": config["selected_case_id"], "native_yield_sign_id": 25,
               "ego_entrance_device": "yield", "non_through_highway": True,
               "ego_approach_road_id": 158208,
               "intersection_polygon_xy_m": [[10, -5], [20, -5], [20, 5], [10, 5]]}
    review = {"marked_stop_line_observed": True, "near_crosswalk_observed": False,
              "reference_boundary": {"source": "marked_stop_line",
                                     "origin_xy_m": [10, 0], "ego_forward_xy": [1, 0]}}
    OUTPUT_ROOT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=OUTPUT_ROOT, prefix="c158208-physical-source-") as folder:
        root = Path(folder)
        (root / "config.json").write_text(json.dumps(config) + "\n")
        (root / "acquisition-provenance.json").write_text(json.dumps({
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}) + "\n")
        ego, other = Body(101, 0), Body(102, 12)
        writer = EntrySourceWriter(root, context, review, ego, other, NS(id=25))
        snapshot = NS(frame=100)
        world = NS(get_snapshot=lambda: snapshot)
        with (root / "trace.jsonl").open("w") as trace:
            for frame, x in ((100, 0), (101, 12), (102, 25)):
                snapshot.frame, ego.x = frame, x
                time_s = frame / 20
                writer.add(world, frame, time_s, {name: frame for name in CAMERAS})
                trace.write(json.dumps({"frame": frame, "time_s": time_s,
                                        "position_m": [x, 0, 0]}) + "\n")
        result = physical_result(root, {"target_checks": [{"matched": True}],
                                        "realized_observables": {}})
        if (result["physical_checks"]["maneuver"]["status"] != "met"
                or result["physical_checks"]["setup"]["status"] != "not_met"
                or result["diagnostic_fixture"] is not True
                or result["physical_acceptance_claimed"] is not False):
            raise ValueError("Own original-tick source shape did not reach runtime classifier")
        (root / "interaction_history.jsonl").unlink()
        rejected = physical_result(root, {"target_checks": [{"matched": True}],
                                          "realized_observables": {}})
        if (rejected["physical_checks"]["maneuver"]["status"] != "unverified"
                or "interaction_history.jsonl" not in
                rejected["physical_checks"]["maneuver"]["missing_evidence"]):
            raise ValueError("Missing own interaction source was not rejected")
    print(json.dumps({"format": "c158208-physical-source-cpu-check",
                      "classifier_maneuver": "met", "three_frame_setup": "not_met",
                      "missing_interaction": "unverified", "diagnostic_fixture": True,
                      "physical_acceptance_claimed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
