"""Check original Native capture completion and lifecycle before saved conversion."""

import argparse
import hashlib
import json
import math
from pathlib import Path

from measure_readiness import FRAMES, lines, sha
from scene import CASES, request


def audit(directory, condition):
    if condition not in CASES:
        raise ValueError("Unknown exact condition")
    root = Path(directory)
    paths = {name: root / name for name in (
        "native-request.json", "native-map-readback.json", "native-capture-report.json",
        "observed-actors.jsonl", "video_frames.jsonl", "scene.xodr")}
    for name, path in paths.items():
        if not path.is_file():
            raise ValueError("Missing original capture source: " + name)
    exact = request(condition)
    if json.loads(paths["native-request.json"].read_text()) != exact:
        raise ValueError("Capture request differs from exact construction")
    if paths["scene.xodr"].read_text().rstrip("\n") != exact["source_map"]:
        raise ValueError("Original OpenDRIVE differs from exact construction")
    map_readback = json.loads(paths["native-map-readback.json"].read_text())
    actual_map_hash = map_readback.get("original_opendrive_sha256")
    if (map_readback.get("requested_map_sha256") != hashlib.sha256(
            exact["source_map"].encode()).hexdigest() or
            map_readback.get("initial_road_id") != exact["road_id"] or
            type(actual_map_hash) is not str or len(actual_map_hash) != 64 or
            any(c not in "0123456789abcdef" for c in actual_map_hash)):
        raise ValueError("Native map readback is incomplete or changed")
    report = json.loads(paths["native-capture-report.json"].read_text())
    if (report.get("case_id") != exact["case_id"] or report.get("frames") != FRAMES or
            report.get("expected_frames") != FRAMES or report.get("error") is not None or
            report.get("accepted") is not False):
        raise ValueError("Native capture report is incomplete or claims acceptance")
    restoration = report.get("restoration")
    if not isinstance(restoration, dict) or restoration.get("restored") is not True:
        raise ValueError("Native world restoration did not pass")
    observed = lines(paths["observed-actors.jsonl"])
    frames = lines(paths["video_frames.jsonl"])
    if len(observed) != FRAMES or len(frames) != FRAMES:
        raise ValueError("Original Native and video frame counts must be 600")
    previous_native, previous_actor_time = -1, None
    for i, (row, frame) in enumerate(zip(observed, frames)):
        native = frame.get("native_frame")
        if (row.get("frame") != i or frame.get("video_frame") != i or
                type(native) is not int or (i and native != previous_native + 1) or
                row.get("native_frame") != native or
                row.get("source_kind") != "original_native_motion"):
            raise ValueError("Original Native and video frame join failed")
        if not isinstance(row.get("actors"), dict) or set(row["actors"]) != {"ego", "emergency"}:
            raise ValueError("Original actor readback missing")
        for name in ("ego", "emergency"):
            actor = row["actors"][name]
            center, body = actor.get("native_center_xy_m"), actor.get("native_body_xy_m")
            if (not isinstance(center, list) or len(center) != 2 or
                    not all(type(x) in (int, float) and math.isfinite(x) for x in center) or
                    not isinstance(body, list) or len(body) < 4 or
                    any(not isinstance(point, list) or len(point) != 2 or
                        not all(type(x) in (int, float) and math.isfinite(x) for x in point)
                        for point in body) or
                    type(actor.get("native_speed_mps")) not in (int, float) or
                    not math.isfinite(actor["native_speed_mps"]) or actor["native_speed_mps"] < 0):
                raise ValueError("Original actor geometry or speed readback missing")
        brake, requested_brake = row.get("ego_brake_observed"), row.get("ego_brake_request")
        if (type(brake) not in (int, float) or not math.isfinite(brake) or
                not 0 <= brake <= 1 or type(requested_brake) not in (int, float) or
                not math.isfinite(requested_brake) or not 0 <= requested_brake <= 1 or
                type(row.get("lamp_state_observed")) is not bool or
                type(row.get("lamp_request")) is not bool):
            raise ValueError("Original brake or lamp readback missing")
        if abs(brake - requested_brake) > .001 or row["lamp_state_observed"] != row["lamp_request"]:
            raise ValueError("Original brake or lamp request/readback mismatch")
        t = frame.get("time_s")
        if type(t) not in (int, float) or not math.isfinite(t) or abs(t - i / 20) > .005:
            raise ValueError("Original video cadence differs from 20 Hz")
        actor_time = row.get("time_s")
        if (type(actor_time) not in (int, float) or not math.isfinite(actor_time) or
                (previous_actor_time is not None and
                 abs(actor_time - previous_actor_time - .05) > .005)):
            raise ValueError("Original Native cadence differs from 20 Hz")
        previous_native = native
        previous_actor_time = actor_time
    return {"format": "original-capture-lifecycle-audit", "case_id": exact["case_id"],
            "sample_count": FRAMES, "restoration_passed": True,
            "source_sha256": {name: sha(path) for name, path in paths.items()},
            "physical_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory")
    parser.add_argument("condition", choices=CASES)
    args = parser.parse_args()
    print(json.dumps(audit(args.directory, args.condition), sort_keys=True))
