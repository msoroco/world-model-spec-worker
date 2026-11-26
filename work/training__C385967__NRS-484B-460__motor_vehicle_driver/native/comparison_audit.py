"""Independent source-hash audit of the controlled at-rest angle comparison."""
import argparse
import json
from pathlib import Path

from saved_angle import ASSIGNMENT, measure, sha


PREFIX = ASSIGNMENT + "__selected_03f318de__condition_"


def audit(left, right, *, allow_fixture=False):
    paths = (Path(left), Path(right))
    fixed = []
    measured = []
    sources = []
    for suffix, requested, path in zip(("a", "b"), (45, 70), paths):
        config_path = path / "config.json"
        if not config_path.is_file():
            raise ValueError("Missing exact comparison config")
        config = json.loads(config_path.read_text())
        case = PREFIX + suffix
        if config.get("case_id") != case or config.get("selected_case_id") != case or \
                config.get("parked_heading_request_deg") != requested:
            raise ValueError("Comparison case or requested angle differs")
        shape = (config.get("law_id"), config.get("cell_id"), config.get("actor"),
            config.get("layout"), config.get("maneuver"), config.get("control"),
            config.get("rate_hz"), config.get("duration_s"),
            config.get("duration_frames"), config.get("device_indicated_angle_deg"),
            config.get("curb_heading_deg"), config.get("space_id"),
            config.get("observed_activity_request"),
            tuple((item.get("name"), item.get("fps"), item.get("width"),
                   item.get("height"), item.get("fov_deg"),
                   tuple(item.get("location_xyz_m", [])),
                   tuple(item.get("rotation_pyr_deg", [])))
                  for item in config.get("cameras", [])))
        if shape[:13] != ("NRS-484B-460", "C385967", "motor_vehicle_driver",
                "one_way_road", "angle_park", "angle_parking_designation",
                20, 30, 600, 45, 0, "angle_space_1", "parked"):
            raise ValueError("Comparison fixed scene changed")
        result = measure(path, case, allow_fixture=allow_fixture)
        fixed.append(shape)
        measured.append(result["mean_measured_angle_to_curb_deg"])
        sources.append(result["source_hashes"])
    if fixed[0] != fixed[1]:
        raise ValueError("Comparison fixed camera or scene conditions differ")
    for name in ("official_device.json", "road_geometry.json"):
        if sources[0][name] != sources[1][name]:
            raise ValueError("Comparison fixed device or curb source changed: " + name)
    if abs(measured[1] - measured[0]) < 1:
        raise ValueError("Requested angle contrast absent in measured at-rest sources")
    return {"format": "c385967-independent-angle-comparison-v1",
        "case_ids": [PREFIX + "a", PREFIX + "b"],
        "fixed_conditions": ["law/cell/actor", "one-way angle-parking scene",
            "official device and curb source hashes", "activity", "20 Hz / 600 frames",
            "four camera names, dimensions, FOV and poses"],
        "deliberate_difference": "parked_heading_relative_to_device_angle",
        "measured_angles_to_curb_deg": measured,
        "measured_difference_deg": measured[1] - measured[0],
        "source_hashes": sources, "diagnostic_fixture": allow_fixture,
        "legal_angle_tolerance_asserted": False,
        "physical_acceptance_claimed": False, "legal_verdict": None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--left-attempt", type=Path, required=True)
    parser.add_argument("--right-attempt", type=Path, required=True)
    parser.add_argument("--allow-fixture", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.left_attempt, args.right_attempt,
        allow_fixture=args.allow_fixture), sort_keys=True))
