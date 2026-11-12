"""Independent saved-source comparison of waiting for green and right on red.

The returned comparison is diagnostic until original Native and pixel evidence
is independently reviewed. Neither branch is assigned a legal verdict here.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "draft-green-release-execution-manifest.json"
RUNS = ROOT / ".runtime-work/c110919-update027-green-matrix"
IDENTITY = {"case_id", "selected_case_id", "supported_case_ids", "case", "case_suffix"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load(suffix, *, diagnostic):
    manifest = read(MANIFEST)
    case_id = HERE.name + "__" + suffix
    entry = next((case for case in manifest["cases"] if case["case_id"] == case_id), None)
    require(entry is not None and entry["kind"] == "draft_not_selected" and
            entry["construction_sha256"] == sha(HERE / entry["construction"]),
            "Green-release primary construction changed")
    run = RUNS / suffix / "primary"
    attempt = run / "compatibility"
    compatibility = read(attempt / "compatibility.json")
    saved_path = run / "saved/v0001/processing.json"
    saved = read(saved_path)
    require(compatibility["passed"] is True and compatibility["case_id"] == case_id and
            compatibility["candidate_id"] == "primary" and
            compatibility["construction_sha256"] == entry["construction_sha256"] and
            saved["passed"] is True and saved["case_id"] == case_id and
            saved["candidate_id"] == "primary" and
            saved["originals_preserved"] is True and
            saved["timestamp_joins"]["passed"] is True and
            saved["physical_acceptance_claimed"] is False and
            saved["legal_acceptance_claimed"] is False,
            "Green-release source or saved receipt incomplete")
    names = ("native_samples.jsonl", "video_frames.jsonl", "capture/evidence.jsonl",
             "trace.jsonl", "road_geometry.json", "road.xodr",
             "overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")
    hashes = {name: sha(attempt / name) for name in names}
    require(all(saved["original_source_hashes"].get(name) == value
                for name, value in hashes.items()),
            "Green-release retained source hash changed")
    samples = rows(attempt / "native_samples.jsonl")
    require(len(samples) == 480 and all(row.get("synthetic_diagnostic") is diagnostic
            and (row.get("speed_provenance") == "synthetic_native_sample") is diagnostic
            for row in samples), "Synthetic green-release source promoted or original mislabeled")
    return {"case_id": case_id, "config": read(attempt / "config.json"),
            "road": read(attempt / "road_geometry.json"), "samples": samples,
            "frames": rows(attempt / "video_frames.jsonl"),
            "evidence": rows(attempt / "capture/evidence.jsonl"),
            "result": read(attempt / "result.json"), "source_sha256": hashes,
            "saved_processing_sha256": sha(saved_path),
            "construction_sha256": entry["construction_sha256"]}


def release_measure(samples, boundary=-14.0):
    require(len(samples) == 480, "Green-release interval incomplete")
    fronts = [max(vertex[1] for vertex in sample["native_body_xy_m"])
              for sample in samples]
    first_stop = next((i for i in range(160) if samples[i]["speed_mps"] <= .05
                       and fronts[i] < boundary), None)
    crossing = next((i for i in range(1, 480)
                     if fronts[i - 1] < boundary <= fronts[i]), None)
    require(first_stop is not None and crossing is not None,
            "Full-body halt or crossing absent")
    held = crossing >= 160 and all(samples[i]["speed_mps"] <= .05 and
                                   fronts[i] < boundary for i in range(first_stop, 160))
    return {"first_stationary_frame": first_stop,
            "first_front_crossing_frame": crossing,
            "remain_stopped_until_green": held}


def compare(left, right, *, diagnostic):
    plan = read(HERE / "case-plan.json")
    declaration = next(row for row in plan["comparisons"] if
                       row["comparison_id"] == HERE.name + "__comparison_green_release")
    require(declaration["case_ids"] == [left["case_id"], right["case_id"]] and
            declaration["deliberate_differences"] == ["remain_stopped_until_green"],
            "Green-release comparison declaration changed")
    stripped = lambda side: {key: value for key, value in side["config"].items()
                             if key not in IDENTITY}
    require(stripped(left) == stripped(right), "Capture or controller config differs")
    require(left["road"] == right["road"] and
            left["source_sha256"]["road.xodr"] == right["source_sha256"]["road.xodr"] and
            left["road"]["stopping_reference_y_m"] == -14.0,
            "Held road or marked stopping reference differs")
    a, b = left["samples"], right["samples"]
    require(len(a) == len(b) == len(left["frames"]) == len(right["frames"]) ==
            len(left["evidence"]) == len(right["evidence"]) == 480,
            "Paired source interval incomplete")
    differences = []
    for i, (x, y, fx, fy, ex, ey) in enumerate(zip(
            a, b, left["frames"], right["frames"], left["evidence"], right["evidence"])):
        expected_signal = "Red" if i < 160 else "Green"
        require(fx == fy and x["native_frame"] == y["native_frame"] == fx["native_frame"] and
                x["time_s"] == y["time_s"] == fx["time_s"] and
                ex.get("world", {}).get("weather") == ey.get("world", {}).get("weather") and
                x["signal_state_observed"] == y["signal_state_observed"] == expected_signal and
                x["walker_conflict_occupied"] == y["walker_conflict_occupied"] and
                x["walker_center_xy_m"] == y["walker_center_xy_m"],
                "Held frame, weather, signal or pedestrian context differs")
        changes = {key for key in set(x) | set(y) if x.get(key) != y.get(key)}
        require(changes <= {"speed_mps", "native_center_xy_m", "native_yaw_deg",
                            "native_body_xy_m"}, "Undeclared paired source difference")
        if changes:
            differences.append(i)
    require(differences and min(differences) >= 130 and max(differences) < 480,
            "Release policy produced no controlled motion difference")
    left_release = release_measure(a)
    right_release = release_measure(b)
    require(left_release["remain_stopped_until_green"] is True and
            right_release["remain_stopped_until_green"] is False and
            left_release["first_front_crossing_frame"] > 160 and
            right_release["first_front_crossing_frame"] < 160 and
            all(left["result"]["measured_values"]["green_release"].get(key) == value
                for key, value in left_release.items()) and
            all(right["result"]["measured_values"]["green_release"].get(key) == value
                for key, value in right_release.items()),
            "Measured green-release outcome differs from retained full-body sources")
    require(all(side["result"].get("accepted") is False and
                side["result"].get("legal_verdict_claimed") is False
                for side in (left, right)), "Comparison claimed acceptance")
    return {"format": "c110919-green-release-saved-comparison-v1",
            "comparison_id": declaration["comparison_id"],
            "case_ids": declaration["case_ids"],
            "declared_differences": declaration["deliberate_differences"],
            "different_motion_frame_range": [min(differences), max(differences)],
            "wait_release": left_release, "red_turn_release": right_release,
            "source_bindings": [{key: side[key] for key in
                                 ("source_sha256", "saved_processing_sha256",
                                  "construction_sha256")} for side in (left, right)],
            "source_comparison_passed": True, "diagnostic_fixture": diagnostic,
            "passed": False, "physical_or_legal_acceptance_claimed": False}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(compare(load("green_release_wait", diagnostic=args.diagnostic),
                             load("green_release_red_turn", diagnostic=args.diagnostic),
                             diagnostic=args.diagnostic), indent=2))
