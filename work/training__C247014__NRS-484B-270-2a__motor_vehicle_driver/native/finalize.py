"""Saved-only source joins and lane-pass measurements; no legal conclusion."""

import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from scene import FRAMES, LEFT_CENTER_Y_M, RIGHT_CENTER_Y_M


CAMERAS = {"overview", "approach", "reference_corner", "driver_reference"}
SOURCES = ("participant-poses.jsonl", "trace.jsonl", "video_frames.jsonl",
           "road.xodr", "pass-context.json", "capture/evidence.jsonl")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def derive(attempt):
    attempt = Path(attempt)
    for name in SOURCES:
        if not (attempt / name).is_file():
            raise ValueError("Missing original source: " + name)
    road = ET.fromstring((attempt / "road.xodr").read_text())
    lanes = road.findall("road/lanes/laneSection/right/lane")
    if [int(l.attrib["id"]) for l in lanes] != [-1, -2]:
        raise ValueError("Original immediate-left lane geometry differs")
    poses, trace, mapping, captures = [rows(attempt / name) for name in
                                     ("participant-poses.jsonl", "trace.jsonl",
                                      "video_frames.jsonl", "capture/evidence.jsonl")]
    if not all(len(x) == FRAMES for x in (poses, trace, mapping, captures)):
        raise ValueError("Full original 600-frame source join required")
    left_frames = []
    pass_frames = []
    blocker_frames = []
    for index, (pose, state, video, captured) in enumerate(zip(poses, trace, mapping, captures)):
        frame = pose.get("frame")
        if (pose.get("video_frame") != index or state.get("frame") != frame or
                video.get("carla_frame") != frame or captured.get("original_frame") != frame):
            raise ValueError("Original frame join differs")
        if set(video.get("camera_native_frames", {})) != CAMERAS or any(
                value != frame for value in video["camera_native_frames"].values()):
            raise ValueError("Original four-camera frame join differs")
        if abs(pose.get("time_s", -10) - video.get("time_s", -20)) > 1e-4:
            raise ValueError("Original time join differs")
        ego, cycle = pose.get("ego"), pose.get("cyclist")
        if not isinstance(ego, dict) or not isinstance(cycle, dict):
            raise ValueError("Original participant pose missing")
        ex, ey = ego["center_xy_m"]
        cx, cy = cycle["center_xy_m"]
        if (ego.get("blueprint_id", "").startswith("vehicle.") is False or
                cycle.get("blueprint_id") != "vehicle.bh.crossbike"):
            raise ValueError("Original motor/cycle identities differ")
        if abs(ey - LEFT_CENTER_Y_M) < .5:
            left_frames.append(index)
        if abs(ex - cx) <= 4:
            pass_frames.append(index)
        if pose.get("left_blocker") is not None:
            blocker_frames.append(index)
    if not pass_frames or pass_frames[0] == 0 or pass_frames[-1] == FRAMES - 1:
        raise ValueError("Original behind-to-ahead pass incomplete")
    context = json.loads((attempt / "pass-context.json").read_text())
    if context.get("statutory_subject") != "bicycle":
        raise ValueError("Covered cycle context missing")
    return {"pass_first_frame": pass_frames[0], "pass_last_frame": pass_frames[-1],
            "first_left_frame": left_frames[0] if left_frames else None,
            "left_during_pass_frames": len(set(left_frames) & set(pass_frames)),
            "pass_frame_count": len(pass_frames),
            "left_blocker_frames": len(blocker_frames),
            "left_lane_available_verified": False,
            "reasonably_safe_judged": False, "due_care_judged": False,
            "physical_completion_accepted": False, "legal_conclusion": None,
            "source_sha256": {name: sha(attempt / name) for name in SOURCES}}


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Retain prior saved result; use fresh output")
    measured = derive(attempt)
    config = json.loads((attempt / "config.json").read_text())
    construction = json.loads((attempt / "construction.json").read_text())
    case = config["case_id"]
    if case != construction["case_id"] or case not in config["supported_case_ids"]:
        raise ValueError("Saved case identity differs")
    poses = rows(attempt / "participant-poses.jsonl")
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    evidence = []
    for channel in construction["recording_description"]["channels"]:
        name = channel["name"]
        if name not in {"ego_pose", "cyclist_pose", "left_lane_occupancy",
                        "drv.overtaking", "drv.lane_change", "rel.occupies"}:
            raise ValueError("Unknown saved channel: " + name)
        path = channels / (name + ".jsonl")
        with path.open("x") as stream:
            for index, pose in enumerate(poses):
                left = abs(pose["ego"]["center_xy_m"][1] - LEFT_CENTER_Y_M) < .5
                if name == "ego_pose":
                    value = pose["ego"]["center_xy_m"]
                elif name == "cyclist_pose":
                    value = pose["cyclist"]["center_xy_m"]
                elif name == "left_lane_occupancy":
                    value = left
                elif name == "drv.overtaking":
                    value = measured["pass_first_frame"] <= index <= measured["pass_last_frame"]
                elif name == "drv.lane_change":
                    value = measured["first_left_frame"] is not None and index == measured["first_left_frame"]
                else:
                    value = "immediate_left" if left else "right"
                stream.write(json.dumps({"time_s": pose["time_s"], "value": value}) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": "channels/" + path.name})
    availability = channels / "left_lane_availability.json"
    availability.write_text(json.dumps({"original_left_blocker_frames": measured["left_blocker_frames"],
                                       "availability_verified": False,
                                       "reasonable_safety_judged": False}) + "\n")
    evidence.append({"name": "left_lane_availability", "unit": "source context",
                     "reference": "channels/left_lane_availability.json"})
    from worker_exchange.native_output import write_result
    write_result(attempt, {
        "case_id": case, "measured_values": measured,
        "target_checks": [{"target": "source-joined immediate-left lane during pass",
                           "requested": True, "measured": True,
                           "method": "original participant poses and road",
                           "tolerance": "original lane review pending", "matched": False,
                           "physical_cause_confirmed": False,
                           "cause_evidence": measured["source_sha256"]}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False, "accepted": False,
        "termination_reason": "Saved measurement only; physical and legal review pending",
        "physical_failure_flags": ["Original lane availability and reasonable safety unreviewed"],
        "trace_reference": "trace.jsonl", "video_references": [
            name + ".mkv" for name in (*sorted(CAMERAS), "raw")],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": construction["recording_description"],
        "recording_evidence": evidence, "realized_observables": {}})
    report = {"format": "worker-analysis-report", "case_id": case,
              "measurements": {"cycle_pass": {"method": "derive", "value": measured,
                                              "sources": measured["source_sha256"]}},
              "source_complete": True, "physical_or_legal_acceptance": False}
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
