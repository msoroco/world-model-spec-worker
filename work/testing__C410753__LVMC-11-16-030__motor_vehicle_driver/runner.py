"""Canonical exact railway case entrypoint and Native operator interface."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from rail_construction import TARGETS
from rail_native_runner import run_case


def load_case(path=None):
    scene = json.loads(Path(path or Path(__file__).with_name("scene.json")).read_text())
    key = scene.get("case_key")
    if (key not in TARGETS or
            scene.get("assignment_id") !=
            "testing__C410753__LVMC-11-16-030__motor_vehicle_driver" or
            scene.get("case_id") != scene["assignment_id"] + "__" + key or
            scene.get("cell_id") != "C410753" or
            scene.get("law_id") != "LVMC-11-16-030" or
            scene.get("actor") != "motor_vehicle_driver" or
            scene.get("target_mph") != TARGETS[key][0] or
            scene.get("obscured_sight_target") is not TARGETS[key][1] or
            scene.get("exception_target") != TARGETS[key][2] or
            scene.get("duration_frames") != 900 or
            scene.get("rate_hz") != 20):
        raise ValueError("exact railway case identity or target differs")
    return scene


def run_native(*, case_path, packet, attempt_root, world, ego,
               location_factory, transform_factory, original_exception_reader,
               camera_adapter, control_factory, brake):
    """Run only with operator-supplied original Native sources and adapters."""
    scene = load_case(case_path)
    if packet.get("assignment_id") != scene["assignment_id"]:
        raise ValueError("rail packet assignment differs")
    return run_case(
        case_key=scene["case_key"], packet=packet, attempt_root=attempt_root,
        world=world, ego=ego, location_factory=location_factory,
        transform_factory=transform_factory,
        original_exception_reader=original_exception_reader,
        camera_adapter=camera_adapter, control_factory=control_factory,
        brake=brake)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=Path, default=Path(__file__).with_name("scene.json"))
    parser.add_argument("--check", action="store_true", required=True)
    args = parser.parse_args()
    scene = load_case(args.case)
    print(json.dumps({"case_id": scene["case_id"],
                      "offline_identity_checked": True,
                      "original_native_site_required_at_capture": True}))


if __name__ == "__main__":
    main()
