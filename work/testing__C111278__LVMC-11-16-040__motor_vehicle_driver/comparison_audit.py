"""Independent saved-source checks for the four exact sight comparisons."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from saved_sight import verify
from sight_measurement import MeasurementError, compare
from sight_construction import MPH_15_MPS


ASSIGNMENT = "testing__C111278__LVMC-11-16-040__motor_vehicle_driver"
PAIRS = {
    "speed_boundary": (("blocked_below", "blocked_at", "blocked_above"), {"traversal_speed"}),
    "sight_condition": (("blocked_at", "clear_at"), {"sight"}),
    "through_exception": (("blocked_at", "through_blocked"), {"through_designation"}),
    "control_exception": (("blocked_at", "controlled_blocked"), {"traffic_controlled"}),
}
FIXED_SOURCES = ("site_source_sha256", "boundary_source_sha256")


def audit(attempts: dict, comparison_id: str) -> dict:
    if comparison_id not in PAIRS:
        raise ValueError("unknown exact sight comparison")
    suffixes, changed = PAIRS[comparison_id]
    if not isinstance(attempts, dict) or set(attempts) != set(suffixes):
        raise ValueError("exact comparison attempt inventory differs")
    measurements = []
    for suffix in suffixes:
        case_id = ASSIGNMENT + "__" + suffix
        saved = verify(Path(attempts[suffix]), case_id)
        value = saved["measurement"]
        if saved["case_id"] != case_id or value["case_id"] != case_id:
            raise ValueError("saved comparison case identity differs")
        cameras = saved.get("camera_capture")
        if (not isinstance(cameras, dict) or
                cameras.get("camera_frames") != 900 or
                cameras.get("camera_images_decoded") != 3600):
            raise ValueError("saved comparison requires four complete original cameras")
        measurements.append(value)
    first = measurements[0]
    for current in measurements[1:]:
        compare(first, current, changed)
        if (first["approach_frame_ids"] != current["approach_frame_ids"] or
                first["traversal_frame_ids"] != current["traversal_frame_ids"]):
            raise MeasurementError("fixed comparison frame windows differ")
        for name in FIXED_SOURCES:
            if first["source_sha256"].get(name) != current["source_sha256"].get(name):
                raise MeasurementError("fixed comparison source changed: " + name)
    if comparison_id == "speed_boundary":
        speeds = [value["traversal_speed_max_mps"] for value in measurements]
        if not (speeds[0] < MPH_15_MPS and
                abs(speeds[1] - MPH_15_MPS) <= .01 and
                speeds[2] > MPH_15_MPS and speeds == sorted(speeds)):
            raise MeasurementError("15 mph below-at-above traversal sequence absent")
    return {"format": "c111278-saved-comparison-audit-v1",
            "comparison_id": comparison_id,
            "case_ids": [value["case_id"] for value in measurements],
            "fixed_source_sha256": {name: first["source_sha256"][name]
                                    for name in FIXED_SOURCES},
            "source_join_passed": True,
            "legal_conclusion": None,
            "physical_visibility_claimed": False}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Audit exact original C111278 comparison")
    parser.add_argument("--comparison", choices=tuple(PAIRS), required=True)
    parser.add_argument("--attempt", type=Path, action="append", required=True,
                        help="repeat in the comparison's declared case order")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    suffixes = PAIRS[args.comparison][0]
    if len(args.attempt) != len(suffixes):
        parser.error("exact ordered comparison attempt count differs")
    output = args.output.resolve()
    if ".runtime-work" not in output.parts or output.exists():
        raise ValueError("new comparison output must be under .runtime-work")
    attempts = dict(zip(suffixes, (path.resolve() for path in args.attempt)))
    value = audit(attempts, args.comparison)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
