"""Synthetic positive and failure checks for the original capture lifecycle audit."""

import copy
import hashlib
import json
from pathlib import Path

from audit_capture import audit
from scene import CASES, request


HERE = Path(__file__).resolve().parent
SCRATCH = HERE.parents[2] / ".runtime-work" / "C405647-capture-proof"


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def reject(name, fragment, change, restore):
    change()
    try:
        audit(SCRATCH, CASES[0])
    except ValueError as error:
        if fragment not in str(error):
            raise AssertionError((name, str(error))) from error
        return str(error)
    finally:
        restore()
    raise AssertionError(name + " accepted invalid capture")


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    exact = request(CASES[0])
    write(SCRATCH / "native-request.json", exact)
    (SCRATCH / "scene.xodr").write_text(exact["source_map"] + "\n")
    write(SCRATCH / "native-map-readback.json", {
        "requested_map_sha256": hashlib.sha256(exact["source_map"].encode()).hexdigest(),
        "original_opendrive_sha256": hashlib.sha256(exact["source_map"].encode()).hexdigest(),
        "initial_road_id": exact["road_id"]})
    report = {"case_id": exact["case_id"], "frames": 600, "expected_frames": 600,
              "error": None, "accepted": False, "restoration": {"restored": True}}
    write(SCRATCH / "native-capture-report.json", report)
    actor = {"native_center_xy_m": [0.0, 0.0],
             "native_body_xy_m": [[-1.0, -1.0], [1.0, -1.0],
                                  [1.0, 1.0], [-1.0, 1.0]],
             "native_speed_mps": 0.0}
    observed = [{"frame": i, "native_frame": i + 30,
                 "source_kind": "original_native_motion",
                 "actors": {"ego": actor, "emergency": actor},
                 "ego_brake_observed": 0.0, "lamp_state_observed": True}
                for i in range(600)]
    frames = [{"video_frame": i, "native_frame": i + 30, "time_s": i / 20}
              for i in range(600)]
    actor_path, frame_path = (SCRATCH / name for name in
                              ("observed-actors.jsonl", "video_frames.jsonl"))
    actor_path.write_text("".join(json.dumps(row) + "\n" for row in observed))
    frame_path.write_text("".join(json.dumps(row) + "\n" for row in frames))
    positive = audit(SCRATCH, CASES[0])
    bad_report = copy.deepcopy(report)
    bad_report["restoration"] = {"restored": False}
    failures = {"failed_restoration": reject("failed_restoration", "restoration did not pass",
        lambda: write(SCRATCH / "native-capture-report.json", bad_report),
        lambda: write(SCRATCH / "native-capture-report.json", report))}
    bad_report = copy.deepcopy(report)
    bad_report["frames"] = 599
    failures["short_capture"] = reject("short_capture", "capture report is incomplete",
        lambda: write(SCRATCH / "native-capture-report.json", bad_report),
        lambda: write(SCRATCH / "native-capture-report.json", report))
    bad = copy.deepcopy(frames)
    bad[100]["native_frame"] += 1
    failures["frame_mismatch"] = reject("frame_mismatch", "frame join failed",
        lambda: frame_path.write_text("".join(json.dumps(row) + "\n" for row in bad)),
        lambda: frame_path.write_text("".join(json.dumps(row) + "\n" for row in frames)))
    bad_actors = copy.deepcopy(observed)
    bad_actors[100]["actors"]["emergency"]["native_body_xy_m"] = []
    failures["missing_body"] = reject("missing_body", "geometry or speed readback missing",
        lambda: actor_path.write_text("".join(json.dumps(row) + "\n" for row in bad_actors)),
        lambda: actor_path.write_text("".join(json.dumps(row) + "\n" for row in observed)))
    wrong = request(CASES[1])
    failures["wrong_case"] = reject("wrong_case", "differs from exact construction",
        lambda: write(SCRATCH / "native-request.json", wrong),
        lambda: write(SCRATCH / "native-request.json", exact))
    assert audit(SCRATCH, CASES[0]) == positive
    print(json.dumps({"passed": True, "positive": positive,
                      "negative_rejections": failures,
                      "synthetic_diagnostic_only": True}, sort_keys=True))


if __name__ == "__main__":
    main()
