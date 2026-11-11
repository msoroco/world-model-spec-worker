"""Three distinct physical-risk alternatives for stopped drive-to 450 ft."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = HERE.name + "__stopped_drive_to_450ft"
FOLDER = HERE / "cases/stopped_drive_to_450ft"


def once(text, before, after):
    if text.count(before) != 1:
        raise ValueError("Stopped candidate knob not unique: " + before)
    return text.replace(before, after)


def main():
    primary = json.loads((FOLDER / "construction.json").read_text())
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    entry = next(item for item in manifest["cases"] if item["case_id"] == CASE)
    variants = [
        ("fallback1", ["runner.py", "stopped_runner.py"],
         "select_crest_route(world.get_map(), target_gap_ft=target + 100)",
         "select_crest_route(world.get_map(), target_gap_ft=target + 100, step_m=2.5)",
         "Native crest route sampling 5 m to 2.5 m",
         {"source": "Native waypoint route-selection diagnostic",
          "metric": "count of stationary-apparatus crest routes supporting a 550 ft initial approach",
          "failure_condition": "Primary 5 m route sampling finds no continuous verified crest approach; use denser Native sampling."}),
        ("fallback2", ["runner.py", "stopped_runner.py"],
         'park=config["fire_branch"] == "stopped_park",\n                         carla_module=carla)',
         'park=config["fire_branch"] == "stopped_park",\n                         gain=0.28, speed_gain=0.32, carla_module=carla)',
         "stopped approach control gains 0.35/0.40 to 0.28/0.32",
         {"source": "original participant_footprints.jsonl and participant_state.jsonl",
          "metric": "measured center-distance overshoot and reversal around the 450 ft command",
          "failure_condition": "Primary approach overshoots its 450 ft engineering target then reverses closing direction; no legal tolerance is inferred."}),
        ("fallback3", ["fire_camera_capture.py"],
         '"approach": ((1.2, 0.0, 2.0), (0.0, 0.0, 0.0), (1280, 720), 90)',
         '"approach": ((1.8, 0.0, 2.3), (0.0, 0.0, 0.0), (1280, 720), 90)',
         "approach camera mount 1.2 m forward/2.0 m high to 1.8 m forward/2.3 m high",
         {"source": "complete decoded approach and overview original RGB streams",
          "metric": "stopped apparatus and ego body visibility over all original frames",
          "failure_condition": "Primary approach view omits a required body in any original frame, confirmed by source-bound pixel review."}),
    ]
    old = {item["id"]: item for item in entry.get("candidates", [])}
    candidates = []
    for ident, paths, before, after, knob, trigger in variants:
        variant = deepcopy(primary)
        for name in paths:
            file = next(item for item in variant["files"] if item["path"] == name)
            file["content"] = once(file["content"], before, after)
        variant["candidate_id"] = ident
        path = FOLDER / (ident + "-construction.json")
        path.write_text(json.dumps(variant, indent=2) + "\n")
        item = {"id": ident,
                "construction": path.relative_to(HERE).as_posix(),
                "construction_sha256": sha256(path.read_bytes()).hexdigest(),
                "trigger": trigger, "changed_knobs": [knob]}
        prior = old.get(ident)
        if prior and prior["construction_sha256"] == item["construction_sha256"]:
            for key in ("offline", "compatibility"):
                if key in prior:
                    item[key] = prior[key]
        candidates.append(item)
    entry["candidates"] = candidates
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
