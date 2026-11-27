"""Offline validation and source-gated Native entry for one exact walking case."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from road_geometry import construction_routes, pedestrian_faces_approach, side_of_highway
from site_source import load_reviewed_site

ASSIGNMENT = "testing__C233658__NRS-484B-297-2__pedestrian"
CAMERAS = {"overview": (1920, 1080), "approach": (1280, 720), "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def check(root: Path) -> dict:
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    spec = json.loads((root / "case-spec.json").read_text(encoding="utf-8"))
    case_id = config.get("selected_case_id")
    expected = ASSIGNMENT + "__" + spec["approach_direction"] + "_approach_" + spec["pedestrian_highway_side"] + "_side"
    if case_id != expected or spec.get("case_id") != expected:
        raise ValueError("walking case identity differs")
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != ("NRS-484B-297-2", "C233658", "pedestrian"):
        raise ValueError("law, cell or actor differs")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 45:
        raise ValueError("20 Hz and 45 seconds required")
    cameras = {camera["name"]: (camera["width"], camera["height"]) for camera in config.get("cameras", [])}
    if cameras != CAMERAS or len(config.get("cameras", [])) != 4:
        raise ValueError("four-camera capture profile differs")
    vehicle, pedestrian = construction_routes(spec["approach_direction"], spec["pedestrian_highway_side"])
    if not pedestrian_faces_approach(vehicle, pedestrian):
        raise ValueError("pedestrian does not face approach")
    observed = side_of_highway(vehicle, pedestrian.start)
    intended = "traffic_right" if spec["pedestrian_highway_side"] == "left" else "traffic_left"
    if observed != intended:
        raise ValueError("pedestrian lateral side differs")
    return {"case_id": case_id, "vehicle_route": [vehicle.start, vehicle.end], "pedestrian_route": [pedestrian.start, pedestrian.end], "source_gate": "reviewed original public highway, sidewalk absence, subsection 6 and map packet required before Native"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=Path.cwd())
    parser.add_argument("--original-site", type=Path)
    args = parser.parse_args()
    result = check(args.output_dir)
    if args.check:
        print(json.dumps({**result, "native_started": False}))
        return
    if args.original_site is None:
        raise ValueError("original reviewed site packet required")
    load_reviewed_site(args.original_site)
    raise RuntimeError("Native capture entry not yet implemented")


if __name__ == "__main__":
    main()
