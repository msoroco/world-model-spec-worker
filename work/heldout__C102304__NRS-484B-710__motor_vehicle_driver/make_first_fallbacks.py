"""Create three engineering alternatives for the same first exact case."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = HERE.name + "__traveling_follow_500ft"


def replace_once(source, before, after):
    if source.count(before) != 1:
        raise ValueError("Expected exactly one candidate engineering knob: " + before)
    return source.replace(before, after)


def main():
    primary = json.loads((HERE / "construction.json").read_text())
    if primary["case_id"] != CASE:
        raise ValueError("Wrong primary construction")
    variants = [
        ("fallback1", "runner.py",
         "select_crest_route(world.get_map(), target_gap_ft=500)",
         "select_crest_route(world.get_map(), target_gap_ft=500, step_m=2.5)",
         "native route waypoint sampling step: 5 m to 2.5 m",
         {"source": "Native waypoint route-selection diagnostic",
          "metric": "count of connected hill-crest spawn routes meeting the original 500 ft construction",
          "failure_condition": "Primary 5 m sampling finds no verified crest route; use denser sampling to resolve available geometry."}),
        ("fallback2", "runner.py",
         "control_step(ego, apparatus, target_gap_ft=500,\n                         carla_module=carla)",
         "control_step(ego, apparatus, target_gap_ft=500,\n                         gain=0.12, speed_gain=0.22, carla_module=carla)",
         "following controller gap/speed gains: 0.18/0.30 to 0.12/0.22",
         {"source": "retained original participant_footprints.jsonl and participant_state.jsonl",
          "metric": "active-frame full-footprint gap oscillation around the commanded 500 ft target",
          "failure_condition": "Primary control produces sustained oscillation outside a predeclared ±2 ft engineering attainment band; this band is not a legal threshold."}),
        ("fallback3", "fire_camera_capture.py",
         '"approach": ((1.2, 0.0, 2.0), (0.0, 0.0, 0.0), (1280, 720), 90)',
         '"approach": ((1.8, 0.0, 2.3), (0.0, 0.0, 0.0), (1280, 720), 90)',
         "approach camera relative mount: 1.2 m forward/2.0 m high to 1.8 m forward/2.3 m high",
         {"source": "complete decoded approach and overview original RGB streams",
          "metric": "required participant body visibility over all original frames",
          "failure_condition": "Primary approach view omits a required participant body in any original frame, confirmed by source-bound pixel review."}),
    ]
    folder = HERE / "cases"
    folder.mkdir(exist_ok=True)
    metadata = []
    for ident, path, before, after, knob, trigger in variants:
        variant = json.loads(json.dumps(primary))
        file = next(item for item in variant["files"] if item["path"] == path)
        file["content"] = replace_once(file["content"], before, after)
        variant["candidate_id"] = ident
        output = folder / (ident + "-construction.json")
        output.write_text(json.dumps(variant, indent=2) + "\n")
        metadata.append({"id": ident, "construction": output.relative_to(HERE).as_posix(),
                         "construction_sha256": sha256(output.read_bytes()).hexdigest(),
                         "trigger": trigger, "changed_knobs": [knob]})
    (HERE / "first-fallbacks.json").write_text(json.dumps(metadata, indent=2) + "\n")


if __name__ == "__main__":
    main()
