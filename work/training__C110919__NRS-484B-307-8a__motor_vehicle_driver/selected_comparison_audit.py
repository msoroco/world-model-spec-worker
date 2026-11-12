"""Independent saved-source stop contrast for the selected right-turn pair."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
IDENTITY = {"case_id", "selected_case_id", "supported_case_ids", "case", "case_suffix"}


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load(suffix, *, diagnostic):
    manifest = read(HERE / "update017-selected-pair-probe-manifest.json")
    case_id = HERE.name + "__" + suffix
    entry = next((item for item in manifest["cases"] if item["case_id"] == case_id), None)
    require(entry is not None and sha(HERE / entry["construction"]) == entry["construction_sha256"],
            "Selected comparison construction changed")
    attempt = ROOT / ".runtime-work/c110919-update017-selected-pair-probe" / suffix / "primary/compatibility"
    saved_path = ROOT / ".runtime-work/c110919-update017-selected-pair-probe" / suffix / "primary/saved/v0001/processing.json"
    saved = read(saved_path)
    require(saved["passed"] is True and saved["originals_preserved"] is True and
            saved["case_id"] == case_id and saved["candidate_id"] == "primary" and
            saved["timestamp_joins"]["passed"] is True,
            "Selected comparison saved processing incomplete")
    source_names = ("native_samples.jsonl", "video_frames.jsonl", "capture/evidence.jsonl",
                    "road_geometry.json", "road.xodr", "config.json")
    hashes = {name: sha(attempt / name) for name in source_names}
    require(all(saved["original_source_hashes"].get(name) == hashes[name]
                for name in source_names if name != "config.json"),
            "Selected comparison original source changed")
    sample = rows(attempt / "native_samples.jsonl")
    require(all(row.get("synthetic_diagnostic") is diagnostic and
                (row.get("speed_provenance") == "synthetic_native_sample") is diagnostic
                for row in sample), "Synthetic comparison source promoted or original source mislabeled")
    return {"case_id": case_id, "config": read(attempt / "config.json"),
            "road": read(attempt / "road_geometry.json"), "samples": sample,
            "frames": rows(attempt / "video_frames.jsonl"),
            "evidence": rows(attempt / "capture/evidence.jsonl"),
            "result": read(attempt / "result.json"), "source_sha256": hashes,
            "saved_processing_sha256": sha(saved_path),
            "construction_sha256": entry["construction_sha256"]}


def compare(left, right, *, diagnostic):
    plan = read(HERE / "case-plan.json")
    comparison = next(item for item in plan["comparisons"] if
                      item["comparison_id"] == HERE.name + "__comparison_main")
    require(comparison["case_ids"] == [left["case_id"], right["case_id"]] and
            comparison["deliberate_differences"] == ["halt_before_nearest_boundary"],
            "Selected comparison declaration differs")
    config = lambda item: {key: value for key, value in item["config"].items()
                           if key not in IDENTITY}
    require(config(left) == config(right), "Held capture or controller config differs")
    require(left["road"] == right["road"] and
            left["source_sha256"]["road.xodr"] == right["source_sha256"]["road.xodr"],
            "Held road geometry differs")
    a, b = left["samples"], right["samples"]
    require(len(a) == len(b) == len(left["frames"]) == len(right["frames"]) ==
            len(left["evidence"]) == len(right["evidence"]) == 480,
            "Selected comparison interval incomplete")
    differences = []
    for index, (x, y, fx, fy, ex, ey) in enumerate(zip(
            a, b, left["frames"], right["frames"], left["evidence"], right["evidence"])):
        require(fx == fy and x["native_frame"] == y["native_frame"] and
                x["time_s"] == y["time_s"] and
                ex.get("world", {}).get("weather") == ey.get("world", {}).get("weather") and
                x["signal_state_observed"] == y["signal_state_observed"] == "Red" and
                x["walker_conflict_occupied"] == y["walker_conflict_occupied"] and
                x["walker_center_xy_m"] == y["walker_center_xy_m"],
                "Held frame, weather, signal or pedestrian context differs")
        changes = {key for key in set(x) | set(y) if x.get(key) != y.get(key)}
        require(changes <= {"speed_mps", "native_center_xy_m", "native_body_xy_m"},
                "Undeclared paired source difference")
        if changes:
            differences.append(index)
    require(differences and min(differences) >= 100 and max(differences) < 170,
            "Controlled stop interval differs")
    stop_a = left["result"]["measured_values"]["stop"]
    stop_b = right["result"]["measured_values"]["stop"]
    require(stop_a["stationary_pre_crossing_frames"] == 30 and
            stop_a["halt_before_nearest_boundary"] is True and
            stop_b["stationary_pre_crossing_frames"] == 0 and
            stop_b["halt_before_nearest_boundary"] is False and
            left["result"]["measured_values"]["turn_yield"] ==
            right["result"]["measured_values"]["turn_yield"],
            "Selected comparison measured outcome differs")
    require(all(item["result"].get("accepted") is False and
                item["result"].get("legal_verdict_claimed") is False
                for item in (left, right)), "Comparison source claimed acceptance")
    return {"format": "c110919-selected-saved-comparison-v1",
            "comparison_id": comparison["comparison_id"],
            "case_ids": comparison["case_ids"],
            "declared_differences": comparison["deliberate_differences"],
            "different_motion_frame_range": [min(differences), max(differences)],
            "reference_stationary_frames": 30, "contrast_stationary_frames": 0,
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
    print(json.dumps(compare(load("reference", diagnostic=args.diagnostic),
                             load("contrast", diagnostic=args.diagnostic),
                             diagnostic=args.diagnostic), indent=2))
