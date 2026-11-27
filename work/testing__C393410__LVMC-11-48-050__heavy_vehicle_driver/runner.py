"""Exact nighttime heavy-truck entrypoint; original sources precede Native use."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from restriction_measure import load_review

ASSIGNMENT = "testing__C393410__LVMC-11-48-050__heavy_vehicle_driver"
CAMERAS = {"overview": [1920, 1080], "approach": [1280, 720],
           "reference_corner": [1280, 720], "driver_reference": [1280, 720]}


def check(root: Path) -> dict:
    root = Path(root).resolve()
    config = json.loads((root / "config.json").read_text())
    spec = json.loads((root / "case-spec.json").read_text())
    control = json.loads((root / "controller.json").read_text())
    case_id = config.get("selected_case_id")
    if (not isinstance(case_id, str) or not case_id.startswith(ASSIGNMENT + "__")
            or spec.get("case_id") != case_id):
        raise ValueError("Selected night truck case differs")
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            "LVMC-11-48-050", "C393410", "heavy_vehicle_driver"):
        raise ValueError("Exact law, cell or actor differs")
    cameras = {row.get("name"): [row.get("width"), row.get("height")]
               for row in config.get("cameras", [])}
    if (config.get("rate_hz") != 20 or config.get("duration_s") != 45
            or len(config.get("cameras", [])) != 4 or cameras != CAMERAS):
        raise ValueError("Four synchronized 20 Hz views required")
    speed = control.get("target_speed_mps")
    if type(speed) not in (int, float) or not 1 <= speed <= 8:
        raise ValueError("Bounded original heavy-vehicle speed required")
    if (spec.get("target_street_class") not in ("non_truck", "truck_route")
            or spec.get("target_district") not in ("residence", "nonresidence")
            or spec.get("target_permit_status") not in (
                "none", "valid", "application_only", "route_condition_breach", "time_condition_breach")):
        raise ValueError("Night truck comparison variable undefined")
    return {"case_id": case_id, "speed": speed,
            "source_gate": "reviewed original unladen weight, district/frontage, route designation, local civil clock and DPW written-permit record required before Native"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=Path.cwd())
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    selected = check(args.output_dir)
    if args.check:
        print(json.dumps({**selected, "native_started": False}))
        return
    packet = args.packet or os.environ.get("C393410_NIGHT_REVIEW_PACKET")
    source_root = args.source_root or os.environ.get("C393410_NIGHT_SOURCE_ROOT")
    if not packet or not source_root:
        raise ValueError("Original reviewed night truck packet and source root required")
    load_review(Path(packet), Path(source_root), selected["case_id"])
    from native_entry import capture_original
    print(json.dumps(capture_original(args.output_dir, args.output_dir, packet, source_root,
                                      host=args.host, port=args.port), sort_keys=True))


if __name__ == "__main__":
    main()
