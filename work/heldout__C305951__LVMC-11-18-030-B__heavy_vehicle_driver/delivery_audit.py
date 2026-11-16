"""Independent saved-source audit for the first heavy marked-lane CPU fixture.

This audits source integrity and measured geometry. It never decides a lawful
lane boundary, either exception, or physical camera visibility.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import subprocess


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CHANNELS = ("native_lane_boundaries", "heavy_vehicle_footprint",
            "lane_boundary_overlap", "passing_context",
            "turn_preparation_context", "four_camera_originals")


def _file(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError("Missing original delivery source: " + name)
    return path


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _decode(path: Path, frames: int) -> dict:
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
         "-show_entries", "stream=nb_read_frames",
         "-of", "default=nokey=1:noprint_wrappers=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    if int(probe.stdout.strip()) != frames:
        raise ValueError("Original camera decoded frame count differs: " + path.name)
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
    return {"sha256": _sha(path), "decoded_frames": frames}


def _clearance(observation: dict) -> float:
    lane = observation["lane"]
    cx, cy = lane["center_xy_m"]
    fx, fy = lane["heading_xy"]
    if abs(fx * fx + fy * fy - 1) > 1e-6 or lane["width_m"] <= 0:
        raise ValueError("Original delivery lane geometry invalid")
    values = []
    for component in observation["heavy_vehicle_components"]:
        corners = component["corners_xy_m"]
        if len(corners) != 4:
            raise ValueError("Original delivery body corners incomplete")
        lateral = [(x - cx) * -fy + (y - cy) * fx for x, y in corners]
        values.extend((lane["width_m"] / 2 - max(lateral),
                       lane["width_m"] / 2 + min(lateral)))
    if not values:
        raise ValueError("Original delivery heavy body absent")
    return min(values)


def audit(root: Path, case_id: str, *, negative_camera: bool = False,
          negative_passing: bool = False, negative_turn: bool = False) -> dict:
    root = Path(root)
    report = json.loads(_file(root, "analysis-report.json").read_text())
    result = json.loads(_file(root, "result.json").read_text())
    if report.get("case_id") != case_id or result.get("case_id") != case_id:
        raise ValueError("Saved delivery case identity differs")
    measurement = report["measurements"]["heavy_lane_footprint"]
    sources = measurement["sources"]
    required = {"native_three_lane_survey.json", "heavy_lane_sources.jsonl",
                "trace.jsonl", "video_frames.jsonl", *(name + ".mkv" for name in CAMERAS)}
    turn_case = case_id.endswith("__lawful_turn_preparation_boundary_crossing")
    if turn_case:
        required.update(("native_turn_plan.json", "turn_intent_sources.jsonl"))
    if set(sources) != required:
        raise ValueError("Saved delivery source inventory differs")
    for name, digest in sources.items():
        actual = name + ".missing" if negative_camera and name == "overview.mkv" else name
        if _sha(_file(root, actual)) != digest:
            raise ValueError("Original delivery source hash differs: " + name)
    survey = json.loads(_file(root, "native_three_lane_survey.json").read_text())
    lanes = {(lane["road_id"], lane["lane_id"]) for lane in survey["lanes"]}
    if len(lanes) != 3:
        raise ValueError("Original delivery three-lane survey differs")
    body = _rows(_file(root, "heavy_lane_sources.jsonl"))
    trace = _rows(_file(root, "trace.jsonl"))
    frame_map = _rows(_file(root, "video_frames.jsonl"))
    samples = measurement["value"]["frames"]
    if not body or len(body) != len(trace) or len(body) != len(frame_map) or len(body) != len(samples):
        raise ValueError("Original delivery frame count differs")
    clearances = []
    for index, (observation, motion, frame, sample) in enumerate(zip(body, trace, frame_map, samples)):
        identity = (observation["frame"], observation["time_s"])
        if (identity != (motion["frame"], motion["time_s"]) or
                identity != (frame["carla_frame"], frame["time_s"]) or
                frame["video_frame"] != index or
                (observation["lane"]["road_id"], observation["lane"]["lane_id"]) not in lanes or
                observation["survey_sha256"] != sources["native_three_lane_survey.json"]):
            raise ValueError("Original delivery body/trace/video join differs")
        value = _clearance(observation)
        if sample["frame"] != identity[0] or sample["time_s"] != identity[1] or sample["minimum_clearance_m"] != value:
            raise ValueError("Saved delivery lane clearance differs from originals")
        clearances.append(value)
    if measurement["value"]["minimum_clearance_m"] != min(clearances):
        raise ValueError("Saved delivery minimum clearance differs")
    passing = report["measurements"].get("passing_context", {}).get("value")
    participant_ids = []
    relative_positions = []
    ego_ids = {part["actor_id"] for row in body for part in row["heavy_vehicle_components"]}
    for index, row in enumerate(body):
        other = None if negative_passing and index == 0 else row.get("overtaken")
        if other is None:
            participant_ids.append(None)
            continue
        actor_id = other.get("actor_id")
        corners = other.get("corners_xy_m")
        velocity = other.get("velocity_xy_mps")
        if (not isinstance(actor_id, int) or actor_id in ego_ids or
                not isinstance(corners, list) or len(corners) != 4 or
                not isinstance(velocity, list) or len(velocity) != 2 or
                any(not isinstance(point, list) or len(point) != 2 or
                    any(not isfinite(float(value)) for value in point)
                    for point in corners) or
                any(not isfinite(float(value)) for value in velocity)):
            raise ValueError("Original passing participant geometry invalid")
        participant_ids.append(actor_id)
        lane = row["lane"]
        fx, fy = lane["heading_xy"]
        ego = row["heavy_vehicle_components"][0]["corners_xy_m"]
        relative_positions.append(sum(x * fx + y * fy for x, y in ego) / 4 -
                                  sum(x * fx + y * fy for x, y in corners) / 4)
    observed_ids = sorted(set(x for x in participant_ids if x is not None))
    if (passing is not None and passing.get("overtaken_actor_ids") != observed_ids or
            observed_ids and (len(set(participant_ids)) != 1 or
                              len(relative_positions) != len(body))):
        raise ValueError("Saved passing participant differs from original source")
    order_reversal = bool(relative_positions and relative_positions[0] < 0 < relative_positions[-1])
    if passing is not None and passing.get("order_reversal_observed") not in (None, order_reversal):
        raise ValueError("Saved passing order reversal differs from originals")
    turn_context = None
    if turn_case:
        plan = json.loads(_file(root, "native_turn_plan.json").read_text())
        intent_rows = _rows(_file(root, "turn_intent_sources.jsonl"))
        reported = report["measurements"]["turn_preparation_context"]["value"]
        if (len(intent_rows) != len(body) or
                reported.get("turn_plan") != plan or
                reported.get("source_frame_count") != len(body) or
                reported.get("lawful_turn_premise") is not None or
                plan.get("lawful_turn_premise") is not None or
                plan.get("requested_movement") != "turn" or
                plan.get("direction") not in ("left", "right")):
            raise ValueError("Saved turn plan differs from originals")
        for index, (row, frame) in enumerate(zip(intent_rows, frame_map)):
            if (row.get("frame") != frame["carla_frame"] or
                    row.get("time_s") != frame["time_s"] or
                    row.get("turn_plan_sha256") != sources["native_turn_plan.json"] or
                    row.get("requested_direction") != plan["direction"] or
                    not row.get("command") or not row.get("indicator_readback") or
                    row.get("lawful_turn_premise") is not None or
                    (negative_turn and index == 0)):
                raise ValueError("Original turn-intent source join differs")
        turn_context = {"requested_direction": plan["direction"],
                        "source_frame_count": len(intent_rows),
                        "lawful_turn_premise": None}
    evidence = {item["name"]: item for item in result["recording_evidence"]}
    if set(evidence) != set(CHANNELS):
        raise ValueError("Saved delivery recording channel inventory differs")
    for name, item in evidence.items():
        channel = _file(root, item["reference"])
        if _sha(channel) != item["sha256"] or len(_rows(channel)) != len(body):
            raise ValueError("Saved delivery derived channel differs: " + name)
    decoded = {name: _decode(_file(root, name + ".mkv"), len(body)) for name in CAMERAS}
    return {"format": "worker-heavy-lane-delivery-audit-fixture", "case_id": case_id,
            "fixture_only": True, "frames": len(body), "source_join_verified": True,
            "minimum_clearance_m": min(clearances), "four_camera_decode": decoded,
            "passing_context": {"overtaken_actor_ids": observed_ids,
                                "order_reversal_observed": order_reversal,
                                "lawful_passing_premise": None},
            "turn_preparation_context": turn_context,
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


def compare_containment(within_root: Path, crossing_root: Path, *,
                        negative_same_body: bool = False) -> dict:
    """Compare the source-measured footprint while checking declared fixed inputs."""
    first = Path(within_root)
    second = first if negative_same_body else Path(crossing_root)
    within = audit(first, json.loads(_file(first, "result.json").read_text())["case_id"])
    crossing = audit(second, json.loads(_file(second, "result.json").read_text())["case_id"])
    if (within["case_id"] == crossing["case_id"] or
            not within["case_id"].endswith("__within_marked_lane") or
            not crossing["case_id"].endswith("__unexcused_boundary_crossing")):
        raise ValueError("Heavy marked-lane comparison case pair differs")
    fixed = ("native_three_lane_survey.json", "video_frames.jsonl",
             "overview.mkv", "approach.mkv", "reference_corner.mkv",
             "driver_reference.mkv")
    for name in fixed:
        if _sha(_file(first, name)) != _sha(_file(second, name)):
            raise ValueError("Heavy marked-lane fixed comparison source differs: " + name)
    body_first = _rows(_file(first, "heavy_lane_sources.jsonl"))
    body_second = _rows(_file(second, "heavy_lane_sources.jsonl"))
    if len(body_first) != len(body_second):
        raise ValueError("Heavy marked-lane comparison sample count differs")
    for left, right in zip(body_first, body_second):
        if left["overtaken"] is not None or right["overtaken"] is not None:
            raise ValueError("Passing context changed in containment comparison")
        if (left["frame"], left["time_s"]) != (right["frame"], right["time_s"]):
            raise ValueError("Heavy marked-lane comparison frame schedule differs")
        components = left["heavy_vehicle_components"], right["heavy_vehicle_components"]
        if len(components[0]) != len(components[1]):
            raise ValueError("Heavy marked-lane component count differs")
        for a, b in zip(*components):
            if a["actor_id"] != b["actor_id"]:
                raise ValueError("Heavy marked-lane component identity differs")
            pa, pb = a["corners_xy_m"], b["corners_xy_m"]
            if len(pa) != 4 or len(pb) != 4:
                raise ValueError("Heavy marked-lane component corners incomplete")
            delta = [pb[0][0] - pa[0][0], pb[0][1] - pa[0][1]]
            if any(abs((q[0] - p[0]) - delta[0]) > 1e-6 or
                   abs((q[1] - p[1]) - delta[1]) > 1e-6
                   for p, q in zip(pa, pb)):
                raise ValueError("Heavy marked-lane body dimensions changed")
    if not within["minimum_clearance_m"] > 0 or not crossing["minimum_clearance_m"] < 0:
        raise ValueError("Heavy marked-lane deliberate footprint difference absent")
    return {"format": "worker-heavy-lane-comparison-fixture",
            "case_ids": [within["case_id"], crossing["case_id"]],
            "fixed_source_sha256": {name: _sha(_file(first, name)) for name in fixed},
            "within_minimum_clearance_m": within["minimum_clearance_m"],
            "crossing_minimum_clearance_m": crossing["minimum_clearance_m"],
            "source_join_verified": True, "physical_acceptance_claimed": False,
            "legal_acceptance_claimed": False}


def compare_passing(crossing_root: Path, passing_root: Path, *,
                    negative_passing: bool = False) -> dict:
    """Check that the source-recorded participant is the declared difference."""
    first, second = Path(crossing_root), Path(passing_root)
    left_case = json.loads(_file(first, "result.json").read_text())["case_id"]
    right_case = json.loads(_file(second, "result.json").read_text())["case_id"]
    left = audit(first, left_case)
    right = audit(second, right_case, negative_passing=negative_passing)
    if (not left_case.endswith("__unexcused_boundary_crossing") or
            not right_case.endswith("__passing_boundary_crossing")):
        raise ValueError("Heavy passing comparison case pair differs")
    fixed = ("native_three_lane_survey.json", "video_frames.jsonl",
             "overview.mkv", "approach.mkv", "reference_corner.mkv",
             "driver_reference.mkv")
    for name in fixed:
        if _sha(_file(first, name)) != _sha(_file(second, name)):
            raise ValueError("Heavy passing fixed source differs: " + name)
    base = _rows(_file(first, "heavy_lane_sources.jsonl"))
    changed = _rows(_file(second, "heavy_lane_sources.jsonl"))
    if len(base) != len(changed):
        raise ValueError("Heavy passing sample count differs")
    for a, b in zip(base, changed):
        for key in ("frame", "time_s", "survey_sha256", "lane", "heavy_vehicle_components"):
            if a[key] != b[key]:
                raise ValueError("Heavy passing fixed source field differs: " + key)
        if a.get("overtaken") is not None or b.get("overtaken") is None:
            raise ValueError("Heavy passing participant difference absent")
    if (abs(left["minimum_clearance_m"] - right["minimum_clearance_m"]) > 1e-9 or
            not right["passing_context"]["overtaken_actor_ids"]):
        raise ValueError("Heavy passing clearance or participant comparison differs")
    return {"format": "worker-heavy-lane-passing-comparison-fixture",
            "case_ids": [left_case, right_case],
            "fixed_source_sha256": {name: _sha(_file(first, name)) for name in fixed},
            "matched_minimum_clearance_m": left["minimum_clearance_m"],
            "overtaken_actor_ids": right["passing_context"]["overtaken_actor_ids"],
            "order_reversal_observed": right["passing_context"]["order_reversal_observed"],
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt")
    parser.add_argument("--case")
    parser.add_argument("--compare-attempt")
    parser.add_argument("--passing-comparison", action="store_true")
    parser.add_argument("--negative-same-body", action="store_true")
    parser.add_argument("--negative-camera", action="store_true")
    parser.add_argument("--negative-passing", action="store_true")
    parser.add_argument("--negative-turn", action="store_true")
    args = parser.parse_args()
    if args.compare_attempt:
        if not args.attempt or args.case:
            parser.error("comparison needs --attempt and --compare-attempt")
        if args.passing_comparison:
            print(json.dumps(compare_passing(Path(args.attempt),
                                             Path(args.compare_attempt),
                                             negative_passing=args.negative_passing), indent=2))
        else:
            print(json.dumps(compare_containment(Path(args.attempt),
                                                 Path(args.compare_attempt),
                                                 negative_same_body=args.negative_same_body), indent=2))
        return
    if not args.attempt or not args.case:
        parser.error("delivery audit needs --attempt and --case")
    print(json.dumps(audit(Path(args.attempt), args.case,
                           negative_camera=args.negative_camera,
                           negative_passing=args.negative_passing,
                           negative_turn=args.negative_turn), indent=2))


if __name__ == "__main__":
    main()
