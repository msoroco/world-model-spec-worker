"""Exact source-gated Native entrypoint for selected NRS 484B.293 cases."""

import argparse
import json
import os
from pathlib import Path

ASSIGNMENT = "testing__C150911__NRS-484B-293__pedestrian"
CAMERAS = {"overview": [1920, 1080], "approach": [1280, 720],
           "reference_corner": [1280, 720], "driver_reference": [1280, 720]}
SUFFIXES = {"forward_right", "forward_left", "reverse_right", "reverse_left",
            "forward_right_obstructed"}


def check(directory):
    root = Path(directory)
    config = json.loads((root / "config.json").read_text())
    spec = json.loads((root / "case-spec.json").read_text())
    controller = json.loads((root / "controller.json").read_text())
    cid = config.get("selected_case_id")
    if cid not in {ASSIGNMENT + "__" + s for s in SUFFIXES} or spec.get("case_id") != cid:
        raise ValueError("selected pedestrian case identity differs")
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "NRS-484B-293", "C150911", "pedestrian"):
        raise ValueError("selected pedestrian law/cell/actor differs")
    cameras = config.get("cameras", [])
    named = {c.get("name"): [c.get("width"), c.get("height")] for c in cameras}
    if config.get("rate_hz") != 20 or config.get("duration_s") != 45 or named != CAMERAS or len(cameras) != 4:
        raise ValueError("four-camera 20 Hz profile differs")
    if spec.get("direction") not in ("forward", "reverse") or spec.get("target_half") not in ("left", "right"):
        raise ValueError("pedestrian direction or relative half unspecified")
    if cid.split("__")[-1] != spec["direction"] + "_" + spec["target_half"] + (
            "_obstructed" if spec["obstacle_context"] == "right_half_obstruction" else ""):
        raise ValueError("selected pedestrian case variables differ")
    speed = controller.get("walker_speed_mps")
    if type(speed) not in (int, float) or not .3 <= speed <= 1.5:
        raise ValueError("bounded pedestrian speed required")
    return {"case_id": cid, "walker_speed_mps": speed,
            "source_gate": "reviewed original C150911 crosswalk and obstacle packet required before Native"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=Path.cwd())
    parser.add_argument("--site-review", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    selected = check(args.output_dir)
    if args.check:
        print(json.dumps({**selected, "native_started": False}))
        return
    source = args.site_review or os.environ.get("C150911_CROSSWALK_REVIEW")
    if not source:
        raise ValueError("Missing required source: reviewed original C150911 crosswalk and obstacle packet")
    from native_entry import run_native
    print(json.dumps(run_native(source, selected["case_id"], args.output_dir,
                                host=args.host, port=args.port,
                                speed=selected["walker_speed_mps"]), sort_keys=True))


if __name__ == "__main__":
    main()
