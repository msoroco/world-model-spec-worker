"""Independent source-bound comparison of the statutory release alternatives."""

import argparse
import hashlib
import json
from pathlib import Path


ASSIGNMENT = "training__C394563__LVMC-11-46-030__motor_vehicle_driver"
GROUPS = {
    "signal_release": ("probe_1", "signal_stopped", "signal_raised"),
    "flagman_release": ("flagman_go", "flagman_left"),
    "person_release": ("person_go", "person_left"),
}
EVENTS = {"probe_1": "signal_removed", "signal_stopped": "signal_stopped",
          "signal_raised": "signal_raised", "flagman_go": "flagman_go",
          "flagman_left": "flagman_left", "person_go": "person_go",
          "person_left": "person_left"}
FIXED_FILES = ("road.xodr", "review-school_lane_source",
               "review-child_identity_source", "review-warning_asset_source",
               "review-municipal_jurisdiction_source")
FIXED_ROWS = ("video_frame", "native_frame", "time_s", "source_cameras",
              "vehicle_center_x_m", "observed_speed_mps", "warning_role",
              "warning_active", "children_about_to_cross_or_crossing",
              "vehicle_actor_id", "warning_actor_id", "child_actor_id",
              "vehicle_center_y_m", "vehicle_length_m", "camera_native_frames")
CAMERAS = {"overview", "approach", "reference_corner", "driver_reference"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(group, sources):
    suffixes = GROUPS[group]
    if set(sources) != set(suffixes):
        raise ValueError("Exact release comparison cases missing")
    data = {}
    for suffix in suffixes:
        folder = Path(sources[suffix])
        required = FIXED_FILES + ("native-rows.jsonl", "video_frames.jsonl")
        if any(not (folder / name).is_file() for name in required):
            raise ValueError("Missing original comparison source: " + suffix)
        rows = [json.loads(line) for line in (folder / "native-rows.jsonl").read_text().splitlines()]
        mapping = [json.loads(line) for line in (folder / "video_frames.jsonl").read_text().splitlines()]
        if len(rows) != 600 or len(mapping) != 600:
            raise ValueError("Incomplete original release capture")
        for index, (row, frame) in enumerate(zip(rows, mapping)):
            if (row.get("video_frame") != index or frame.get("video_frame") != index or
                    row.get("native_frame") != frame.get("native_frame") or
                    set(row.get("source_cameras", {})) != CAMERAS or
                    row.get("camera_native_frames") != {name: frame["native_frame"] for name in CAMERAS}):
                raise ValueError("Four-camera original frame join differs")
            if row.get("release_event") != (EVENTS[suffix] if index == 250 else None):
                raise ValueError("Requested release event not independently observed")
            if index < 250 and (not row.get("warning_active") or row.get("observed_speed_mps") != 0.0 and index >= 120):
                raise ValueError("Warning stop or hold absent before release")
        data[suffix] = {"rows": rows, "files": {name: sha(folder / name) for name in required}}
    reference = data[suffixes[0]]
    for suffix in suffixes[1:]:
        candidate = data[suffix]
        for name in FIXED_FILES:
            if candidate["files"][name] != reference["files"][name]:
                raise ValueError("Fixed school warning source differs: " + name)
        for index, (first, second) in enumerate(zip(reference["rows"], candidate["rows"])):
            for key in FIXED_ROWS:
                if first.get(key) != second.get(key):
                    raise ValueError("Fixed release comparison condition differs: " + key + " at " + str(index))
            if index < 250 and first.get("warning_xyz_m") != second.get("warning_xyz_m"):
                raise ValueError("Warning actor differs before release")
        if (reference["rows"][250].get("warning_xyz_m") ==
                candidate["rows"][250].get("warning_xyz_m")):
            raise ValueError("Release actor state does not differ")
    return {"format": "worker-school-release-comparison-audit-v1",
            "comparison_id": ASSIGNMENT + "__" + group,
            "case_ids": [ASSIGNMENT + "__" + suffix for suffix in suffixes],
            "source_hashes": {suffix: item["files"] for suffix, item in data.items()},
            "fixed_conditions_checked": list(FIXED_FILES) + list(FIXED_ROWS) +
                ["warning_actor_before_release", "observed_stop_until_release"],
            "deliberate_difference": "source_observed_release_event_and_warning_actor_state",
            "physical_or_legal_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", choices=GROUPS, required=True)
    parser.add_argument("--source", action="append", required=True,
                        help="SUFFIX=original source directory")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = dict(item.split("=", 1) for item in args.source)
    result = audit(args.group, paths)
    if args.output.exists():
        raise ValueError("Retain prior release comparison audit")
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": True, "comparison_id": result["comparison_id"]}))
