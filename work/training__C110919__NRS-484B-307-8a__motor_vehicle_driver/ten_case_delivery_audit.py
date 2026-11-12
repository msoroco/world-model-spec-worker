"""Independent source boundary for the ten-case red-signal CPU probe.

Diagnostic mode checks retained source shape and always returns nonacceptance.
Original mode requires a separate Native and pixel review before any receipt.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def frames(path):
    command = ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
               "-show_entries", "stream=nb_read_frames",
               "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=120, check=False)
    require(result.returncode == 0 and result.stdout.strip().isdigit(),
            "Source camera decode failed: " + path.name)
    return int(result.stdout.strip())


def audit(case_id, construction_sha256, attempt, processing, *, diagnostic, source_review=None):
    suffix = case_id.removeprefix(HERE.name + "__")
    manifest_path = HERE / "update038-ten-case-probe-manifest.json"
    manifest = read(manifest_path)
    entry = next((x for x in manifest["cases"] if x["case_id"] == case_id), None)
    require(entry is not None and entry.get("kind") == "delivery" and
            manifest.get("case_plan_sha256") == sha(HERE / "case-plan.json"),
            "Case or current plan missing from ten-case probe")
    require(entry["construction_sha256"] == construction_sha256 and
            sha(HERE / entry["construction"]) == construction_sha256,
            "Delivery construction differs from selected manifest")
    attempt = attempt.resolve()
    processing = processing.resolve()
    require(attempt.is_dir() and processing.is_file() and
            (ROOT / ".runtime-work" in attempt.parents if diagnostic else ROOT in attempt.parents),
            "Delivery attempt or saved processing path invalid")
    saved = read(processing)
    require(saved.get("case_id") == case_id and saved.get("candidate_id") == "primary" and
            saved.get("passed") is True and saved.get("originals_preserved") is True and
            saved.get("timestamp_joins", {}).get("passed") is True and
            saved.get("physical_acceptance_claimed") is False and
            saved.get("legal_acceptance_claimed") is False,
            "Saved processing source chain incomplete")
    names = ("native_samples.jsonl", "road_geometry.json", "video_frames.jsonl",
             "capture/evidence.jsonl", "body_history.jsonl", "trace.jsonl",
             *(name + ".mkv" for name in CAMERAS))
    hashes = {}
    for name in names:
        path = attempt / name
        require(path.is_file(), "Missing delivery source: " + name)
        digest = sha(path)
        require(saved.get("original_source_hashes", {}).get(name) == digest,
                "Saved original source changed: " + name)
        hashes[name] = digest
    mapping = rows(attempt / "video_frames.jsonl")
    native = rows(attempt / "native_samples.jsonl")
    evidence = rows(attempt / "capture/evidence.jsonl")
    body = rows(attempt / "body_history.jsonl")
    require(len(mapping) == len(native) == len(evidence) == len(body) == 480,
            "Original participant or frame source missing")
    for index, (frame, sample, capture, physical_body) in enumerate(zip(mapping, native, evidence, body)):
        require(frame["video_frame"] == index and frame["native_frame"] == sample["native_frame"] ==
                capture["original_frame"] == physical_body["frame"] and
                abs(frame["time_s"] - sample["time_s"]) <= 1e-4 and
                len(physical_body["body_vertices_m"]) == 8 and
                {tuple(v) for v in sample["native_body_xy_m"]} ==
                {tuple(v[:2]) for v in physical_body["body_vertices_m"]},
                "Original Native body/time join differs")
    counts = {name: frames(attempt / (name + ".mkv")) for name in CAMERAS}
    require(set(counts.values()) == {480}, "Source camera frame count differs")
    result = read(attempt / "result.json")
    require(saved.get("result_sha256") == sha(attempt / "result.json") and
            result.get("case_id") == case_id and result.get("accepted") is False and
            result.get("legal_verdict_claimed") is False,
            "Saved Native result changed or claims acceptance")
    road = read(attempt / "road_geometry.json")
    if suffix.startswith("absent_reference"):
        require(road.get("stopping_reference_kind") == "intersection_boundary" and
                road.get("stopping_reference_y_m") == road.get("intersection_near_y_m") == -7.0 and
                road.get("stop_line_y_m") is None and
                road.get("nearest_crosswalk_y_m") is None,
                "Absent-reference road source still has a stopping object")
    elif suffix.startswith("green_release"):
        require(road.get("stopping_reference_kind") == "marked_stop_line" and
                road.get("stopping_reference_y_m") == road.get("stop_line_y_m") == -14.0 and
                all(row.get("signal_state_observed") in ("Red", "TrafficLightState.Red")
                    for row in native[:160]) and
                all(row.get("signal_state_observed") in ("Green", "TrafficLightState.Green")
                    for row in native[160:]),
                "Green-release marked line or observed signal transition differs")
        from green_release_physical import classify as classify_green_release
        physical = classify_green_release(native, road, suffix,
                                          provenance_kind=result.get("provenance_kind"),
                                          diagnostic_fixture=diagnostic)
        expected_status = "unverified" if diagnostic else "met"
        require(physical["physical_checks"]["green_release_right_turn"]["status"] == expected_status,
                "Green-release original physical completion or diagnostic provenance differs")
    elif suffix.startswith("yield_"):
        require(road.get("stop_line_y_m") == -14.0 and
                road.get("nearest_crosswalk_y_m") == -11.0 and
                result.get("measured_values", {}).get("signal", {}).get(
                    "stopping_reference_kind") == "marked_stop_line" and
                all(row.get("signal_state_observed") in ("Red", "TrafficLightState.Red")
                    for row in native),
                "Pedestrian-yield marked stop or red signal differs")
        from yield_branch_comparison import measure
        measured = measure(native, suffix)
        branch = result.get("measured_values", {}).get("yield_branch", {})
        require(all(branch.get(name) == measured[name] for name in
                    ("first_body_conflict_frame", "first_pedestrian_conflict_frame",
                     "last_pedestrian_conflict_frame", "body_pedestrian_overlap_frames")),
                "Saved pedestrian and full-body occupancy differs")
        require((not measured["body_pedestrian_overlap_frames"]) ==
                (suffix == "yield_wait"),
                "Pedestrian conflict contrast differs")
    elif suffix.startswith("traffic_"):
        require(road.get("stop_line_y_m") == -14.0 and
                road.get("nearest_crosswalk_y_m") == -11.0 and
                road.get("cross_traffic_signal_actor_id") == 602 and
                road.get("lanes", {}).get("west_traffic_right", {}).get("lane_id") == -1 and
                result.get("measured_values", {}).get("signal", {}).get(
                    "stopping_reference_kind") == "marked_stop_line" and
                all(row.get("signal_state_observed") in ("Red", "TrafficLightState.Red") and
                    row.get("other_traffic_signal_state_observed") in
                    ("Green", "TrafficLightState.Green") for row in native),
                "Other-traffic directed signal, road or marked stop differs")
        from traffic_branch_comparison import measure
        measured = measure(native, suffix)
        branch = result.get("measured_values", {}).get("traffic_branch", {})
        require(all(branch.get(name) == measured[name] for name in
                    ("first_ego_body_conflict_frame", "first_other_traffic_conflict_frame",
                     "last_other_traffic_conflict_frame", "body_traffic_overlap_frames")),
                "Saved directed-traffic and ego full-body occupancy differs")
        require((not measured["body_traffic_overlap_frames"]) ==
                (suffix == "traffic_yield_wait"),
                "Other-traffic conflict contrast differs")
    else:
        require(road.get("stopping_reference_y_m", road.get("stop_line_y_m")) == -14.0,
                "Marked stopping reference differs")
    synthetic = any(row.get("synthetic_diagnostic") is True or
                    row.get("speed_provenance") == "synthetic_native_sample" for row in native)
    if diagnostic:
        require(synthetic and result.get("provenance_kind") == "synthetic_local_diagnostic" and
                result.get("maneuver_completed") is False,
                "Diagnostic source attempted physical promotion")
        return {"format": "worker-delivery-audit", "case_id": case_id,
                "candidate_id": "primary", "passed": False, "source_shaped_unit_test": True,
                "checks": {name: False for name in CHECKS},
                "source_sha256": hashes, "source_frame_counts": counts,
                "source_shape_passed": True, "physical_or_legal_acceptance_claimed": False}
    require(not synthetic and result.get("provenance_kind") == "native" and
            result.get("maneuver_completed") is True and source_review is not None,
            "Original Native motion or independent review missing")
    review = read(source_review)
    require((ROOT / "state/operations").resolve() in source_review.resolve().parents,
            "Original review must be adopted into local operations")
    sys.path.insert(0, str(ROOT / "runtime/pipeline"))
    from scenario_pipeline.worker_exchange.media import audit as decode
    decoded = {name: decode(attempt / (name + ".mkv"), 480,
                            mapping_sha256=hashes["video_frames.jsonl"])
               for name in CAMERAS}
    views = review.get("views", {})
    require(set(views) == set(CAMERAS) and all(
                views[name].get("video_sha256") == hashes[name + ".mkv"] and
                views[name].get("rgb_sequence_sha256") == decoded[name]["rgb_sequence_sha256"] and
                views[name].get("reviewed_frame_ids") == list(range(480)) and
                views[name].get("limitations") is not None
                for name in CAMERAS),
            "Original four-camera pixel review missing or decode changed")
    require(review.get("source_kind") == "original_native_map_signal_actor_pixels" and
            review.get("case_id") == case_id and review.get("reviewer") and
            review.get("method") and review.get("source_sha256") == hashes and
            review.get("signal_governs_ego") is True and
            review.get("stop_reference_confirmed") is True and
            review.get("extreme_right_and_receiving_road_confirmed") is True and
            review.get("pedestrians_and_cross_traffic_reviewed") is True and
            review.get("four_camera_pixels_reviewed") is True and
            review.get("native_owner_released") is True and
            review.get("legal_verdict_claimed") is False,
            "Independent original signal, actor, road or pixel review incomplete")
    if suffix.startswith("absent_reference"):
        require(review.get("nearest_side_reference_absence_confirmed") is True,
                "Original crosswalk, sign and marking absence review missing")
    if suffix.startswith("green_release"):
        require(review.get("green_signal_transition_confirmed") is True and
                review.get("stop_and_release_timing_confirmed") is True,
                "Original green transition or release timing review missing")
    if suffix.startswith("yield_"):
        require(review.get("pedestrian_signal_direction_confirmed") is True and
                review.get("pedestrian_conflict_timing_confirmed") is True and
                review.get("full_body_occupancy_reviewed") is True,
                "Original pedestrian signal or body conflict review missing")
    if suffix.startswith("traffic_"):
        require(review.get("other_traffic_signal_direction_confirmed") is True and
                review.get("other_traffic_conflict_timing_confirmed") is True and
                review.get("other_traffic_full_body_occupancy_reviewed") is True,
                "Original directed traffic signal or full-body review missing")
    return {"format": "worker-delivery-audit", "case_id": case_id,
            "candidate_id": "primary", "passed": True,
            "checks": {name: True for name in CHECKS},
            "source_sha256": hashes, "source_frame_counts": counts,
            "source_review_sha256": sha(source_review),
            "legal_verdict_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--construction-sha256", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--processing", type=Path, required=True)
    parser.add_argument("--source-review", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    receipt = audit(args.case, args.construction_sha256, args.attempt,
                    args.processing, diagnostic=args.diagnostic,
                    source_review=args.source_review)
    require(not args.output.exists(), "Retain previous independent delivery audit")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"case_id": args.case, "source_shape_passed":
                      receipt.get("source_shape_passed", False),
                      "delivery_passed": receipt["passed"]}))


if __name__ == "__main__":
    main()
