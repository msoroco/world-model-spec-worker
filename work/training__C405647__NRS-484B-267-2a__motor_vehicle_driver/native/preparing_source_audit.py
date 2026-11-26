"""Independent original-source review for the preparing-to-move alternatives.

This checks provenance and frame joins. A passing diagnostic fixture is only a
software proof; production review also needs the sealed Native attempt.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys

from branch_alternatives import classify


BASE = "training__C405647__NRS-484B-267-2a__motor_vehicle_driver__preparing_to_move__"
BRANCHES = ("visible_vehicle_movement", "visible_driver_hand_signal")
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
FRAMES = 600
RATE = 20


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    require(root in path.parents and path.is_file(), "Missing or escaping source: " + relative)
    return path


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def audit_structure(attempt, review):
    root = Path(attempt).resolve()
    branch = review.get("activation_branch")
    case = review.get("case_id")
    require(branch in BRANCHES and case == BASE + branch, "Exact preparing branch differs")
    require(review.get("source_kind") == "original_native_observation",
            "Original Native source required")
    hashes = review.get("source_sha256", {})
    required = {"video_frames.jsonl", "preparing_observations.jsonl", "primary.mkv",
                *(view + ".mkv" for view in VIEWS)}
    require(required <= set(hashes), "Original source inventory incomplete")
    for name, expected in hashes.items():
        require(digest(source(root, name)) == expected, "Original source hash changed: " + name)
    mapping = rows(source(root, "video_frames.jsonl"))
    observed = rows(source(root, "preparing_observations.jsonl"))
    require(len(mapping) == len(observed) == FRAMES, "Original preparing duration differs")
    seen = set()
    reach = None
    speeds = []
    vehicle_speeds = []
    for index, (frame, state) in enumerate(zip(mapping, observed)):
        require(frame.get("video_frame") == state.get("video_frame") == index
                and frame.get("native_frame") == state.get("native_frame")
                and abs(frame.get("time_s", -1) - index / RATE) < 1e-6
                and abs(state.get("time_s", -1) - index / RATE) < 1e-6,
                "Original preparing frame and time join differs")
        require(state.get("case_id") == case
                and state.get("source_kind") == "original_native_observation",
                "Original preparing observation identity differs")
        require(state.get("camera_frames") == {view: frame["native_frame"] for view in VIEWS},
                "Original four-camera join differs")
        ego = state.get("ego", {})
        vehicle = state.get("qualifying_vehicle", {})
        require(ego.get("actor_id") and vehicle.get("actor_id")
                and ego["actor_id"] != vehicle["actor_id"],
                "Original preparing participants missing")
        if state.get(branch):
            require(vehicle["actor_id"] == review.get("pixel_review", {}).get("vehicle_actor_id"),
                    "Visible indication belongs to another vehicle")
            if branch == "visible_driver_hand_signal":
                require(state.get("hand_signal_driver_actor_id") ==
                        review.get("pixel_review", {}).get("driver_actor_id"),
                        "Visible hand signal belongs to another driver")
        values = (ego.get("road_x_m"), ego.get("speed_mps"),
                  vehicle.get("road_x_m"), vehicle.get("speed_mps"))
        require(all(type(value) in (int, float) and math.isfinite(value)
                    for value in values) and ego["speed_mps"] >= 0
                and vehicle["speed_mps"] >= 0,
                "Original preparing motion measurement missing")
        if reach is None and ego["road_x_m"] >= vehicle["road_x_m"]:
            reach = index
        speeds.append(ego["speed_mps"])
        vehicle_speeds.append(vehicle["speed_mps"])
        if state.get(branch):
            seen.add(index)
    require(seen and 0 < min(seen) < FRAMES - 1,
            "Visible preparing indication absent or lacks a stationary prelude")
    require(all(speed <= 0.05 for speed in vehicle_speeds[:min(seen)]),
            "Preparing case was already moving before visible indication")
    if branch == "visible_vehicle_movement":
        require(any(speed > 0.05 for speed in vehicle_speeds[min(seen):reach or FRAMES]),
                "Visible vehicle movement has no observed motion")
    require(reach is not None and min(seen) < reach < FRAMES - 20,
            "Approach and pass do not follow visible preparation")
    indication = review.get("pixel_review", {})
    require(indication.get("source_video_sha256") == hashes["primary.mkv"]
            and indication.get("reviewer") and indication.get("review_method")
            and indication.get("branch") == branch
            and indication.get("visible") is True
            and indication.get("vehicle_actor_id")
            and indication.get("first_visible_frame") in seen,
            "Original visible preparation pixel review missing")
    if branch == "visible_driver_hand_signal":
        require(indication.get("driver_actor_id")
                and indication.get("hand_signal_type")
                and indication.get("hand_signal_actor_source_id"),
                "Original driver hand signal pixel review missing")
    witness = dict(review.get("source_witness", {}))
    witness.update(case_id=case, source_kind="original_native_observation",
                   already_moving=False,
                   visible_vehicle_movement=branch == "visible_vehicle_movement",
                   visible_driver_hand_signal=branch == "visible_driver_hand_signal")
    if branch == "visible_vehicle_movement":
        witness["movement_pixel_source_id"] = "primary.mkv:" + str(indication["first_visible_frame"])
    else:
        witness["hand_signal_pixel_source_id"] = "primary.mkv:" + str(indication["first_visible_frame"])
        witness["hand_signal_actor_source_id"] = indication["hand_signal_actor_source_id"]
    classification = classify(witness)
    require(classification["observed_activation_branches"] == [branch],
            "Original source activates another branch")
    return {"case_id": case, "activation_branch": branch, "frames": FRAMES,
            "first_visible_frame": indication["first_visible_frame"],
            "first_reach_frame": reach,
            "initial_approach_speed_mps": sum(speeds[:40]) / 40,
            "last_approach_speed_mps": sum(speeds[reach - 20:reach]) / 20,
            "passing_speed_mps": sum(speeds[reach:reach + 20]) / 20,
            "vehicle_speed_before_visible_mps": max(vehicle_speeds[:min(seen)]),
            "vehicle_speed_after_visible_mps": max(vehicle_speeds[min(seen):reach]),
            "source_sha256": hashes, "classification": classification,
            "reasonable_and_proper_legally_determined": False,
            "physical_completion_claimed": False, "legal_outcome_claimed": False}


def audit(attempt, review):
    result = audit_structure(attempt, review)
    root = Path(attempt).resolve()
    seal = json.loads(source(root, "capture-seal.json").read_text())
    native_result = json.loads(source(root, "result.json").read_text())
    require(seal.get("provenance_kind") == "native"
            and seal.get("diagnostic_fixture") is False
            and seal.get("frames") == FRAMES
            and seal.get("restoration", {}).get("restored") is True
            and all(seal.get("sources", {}).get(name) == expected
                    for name, expected in result["source_sha256"].items()
                    if name in {"video_frames.jsonl", "preparing_observations.jsonl", "primary.mkv",
                                *(view + ".mkv" for view in VIEWS)}),
            "Native capture seal does not verify original acquisition")
    require(native_result.get("case_id") == result["case_id"]
            and native_result.get("provenance_kind") == "original_native"
            and not native_result.get("cpu_harness_only"),
            "Original Native result identity differs")
    require(review.get("auditor_mode") == "original_independent_review",
            "Synthetic or delegated review cannot establish delivery")
    require(".runtime-work" in os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", ""),
            "SCENARIO_PIPELINE_OUTPUT_ROOT must be under .runtime-work")
    repo = Path(__file__).resolve().parents[3]
    receipt = Path(review.get("source_decode_receipt_path", "")).resolve()
    require(receipt.is_file() and repo / ".runtime-work" in receipt.parents,
            "Source decode receipt must live in independent local scratch")
    sys.path.insert(0, str(repo / "runtime"))
    from scenario_pipeline.worker_exchange.media import verify_receipt
    verify_receipt(source(root, "primary.mkv"), receipt, FRAMES,
                   mapping_sha256=result["source_sha256"]["video_frames.jsonl"])
    result["physical_completion_claimed"] = False
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--review", required=True)
    args = parser.parse_args()
    record = json.loads(Path(args.review).read_text())
    require(args.case == record.get("case_id"), "Exact preparing case differs")
    print(json.dumps(audit(args.attempt, record), indent=2, sort_keys=True))
