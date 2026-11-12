"""Independent saved-source contrast for the authored no-reference right turn."""
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "draft-absent-reference-execution-manifest.json"
RUNS = ROOT / ".runtime-work/c110919-update025-absent-matrix"
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


def stop_measure(samples, boundary=-7.0):
    require(len(samples) == 480, "Absent-reference sample interval incomplete")
    fronts = [max(vertex[1] for vertex in sample["native_body_xy_m"])
              for sample in samples]
    crossing = next((i for i in range(1, len(fronts))
                     if fronts[i - 1] < boundary <= fronts[i]), None)
    require(crossing is not None, "Full-body intersection crossing absent")
    stationary = [i for i in range(crossing)
                  if samples[i]["speed_mps"] <= .05 and fronts[i] < boundary]
    return {"stopping_reference_y_m": boundary,
            "first_front_crossing_frame": crossing,
            "stationary_pre_crossing_frames": len(stationary),
            "halt_before_nearest_boundary": bool(stationary)}


def load(suffix, *, diagnostic):
    require(suffix in ("absent_reference", "absent_reference_contrast"), "Unexpected case")
    manifest = read(MANIFEST)
    case_id = HERE.name + "__" + suffix
    entry = next((case for case in manifest["cases"] if case["case_id"] == case_id), None)
    require(entry is not None and entry["kind"] == "draft_not_selected" and
            entry["construction_sha256"] == sha(HERE / entry["construction"]),
            "Absent-reference primary construction changed")
    run = RUNS / suffix / "primary"
    attempt = run / "compatibility"
    compatibility = read(attempt / "compatibility.json")
    saved_path = run / "saved/v0001/processing.json"
    saved = read(saved_path)
    require(compatibility["passed"] is True and compatibility["case_id"] == case_id and
            compatibility["candidate_id"] == "primary" and
            compatibility["construction_sha256"] == entry["construction_sha256"] and
            saved["passed"] is True and saved["case_id"] == case_id and
            saved["candidate_id"] == "primary" and saved["originals_preserved"] is True and
            saved["timestamp_joins"]["passed"] is True and
            saved["physical_acceptance_claimed"] is False and
            saved["legal_acceptance_claimed"] is False,
            "Absent-reference source or saved receipt incomplete")
    names = ("native_samples.jsonl", "video_frames.jsonl", "capture/evidence.jsonl",
             "trace.jsonl", "road_geometry.json", "road.xodr", "overview.mkv",
             "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")
    hashes = {name: sha(attempt / name) for name in names}
    require(all(saved["original_source_hashes"].get(name) == value
                for name, value in hashes.items()), "Retained absent-reference source changed")
    samples = rows(attempt / "native_samples.jsonl")
    require(len(samples) == 480 and all(row.get("synthetic_diagnostic") is diagnostic and
            (row.get("speed_provenance") == "synthetic_native_sample") is diagnostic
            for row in samples), "Synthetic source promoted or original mislabeled")
    xml = ET.fromstring((attempt / "road.xodr").read_text())
    approach = next(x for x in xml.findall("road") if x.attrib["id"] == "1")
    require(not approach.findall("objects/object") and
            len(xml.findall(".//signal[@id='601']")) == 1,
            "Authored absent-reference road or signal changed")
    return {"case_id": case_id, "config": read(attempt / "config.json"),
            "road": read(attempt / "road_geometry.json"), "samples": samples,
            "frames": rows(attempt / "video_frames.jsonl"),
            "evidence": rows(attempt / "capture/evidence.jsonl"),
            "result": read(attempt / "result.json"), "source_sha256": hashes,
            "saved_processing_sha256": sha(saved_path),
            "construction_sha256": entry["construction_sha256"]}


def compare(left, right, *, diagnostic):
    declaration = next(row for row in read(HERE / "case-plan.json")["comparisons"] if
                       row["comparison_id"] == HERE.name + "__comparison_absent_reference")
    require(declaration["case_ids"] == [left["case_id"], right["case_id"]] and
            declaration["deliberate_differences"] ==
            ["halt_before_intersection_when_no_crosswalk_sign_or_marking"],
            "Absent-reference comparison declaration changed")
    stripped = lambda side: {key: value for key, value in side["config"].items()
                             if key not in IDENTITY}
    require(stripped(left) == stripped(right), "Capture or controller config differs")
    road = left["road"]
    require(road == right["road"] and
            left["source_sha256"]["road.xodr"] == right["source_sha256"]["road.xodr"] and
            road["stopping_reference_kind"] == "intersection_boundary" and
            road["stopping_reference_y_m"] == -7.0 and
            road.get("stop_line_y_m") is None and
            road.get("nearest_crosswalk_y_m") is None,
            "Held absent-reference road differs")
    a, b = left["samples"], right["samples"]
    require(len(a) == len(b) == len(left["frames"]) == len(right["frames"]) ==
            len(left["evidence"]) == len(right["evidence"]) == 480,
            "Paired source interval incomplete")
    differences = []
    for i, (x, y, fx, fy, ex, ey) in enumerate(zip(
            a, b, left["frames"], right["frames"], left["evidence"], right["evidence"])):
        require(fx == fy and x["native_frame"] == y["native_frame"] == fx["native_frame"] and
                x["time_s"] == y["time_s"] == fx["time_s"] and
                ex.get("world", {}).get("weather") == ey.get("world", {}).get("weather") and
                x["signal_state_observed"] == y["signal_state_observed"] == "Red" and
                x["walker_conflict_occupied"] == y["walker_conflict_occupied"] and
                x["walker_center_xy_m"] == y["walker_center_xy_m"],
                "Held frame, weather, signal or pedestrian context differs")
        changes = {key for key in set(x) | set(y) if x.get(key) != y.get(key)}
        require(changes <= {"speed_mps", "native_center_xy_m", "native_body_xy_m"},
                "Undeclared paired source difference")
        if changes:
            differences.append(i)
    require(differences and min(differences) >= 100 and max(differences) < 170,
            "Controlled stop interval differs")
    stop_a = stop_measure(a)
    stop_b = stop_measure(b)
    require(left["result"]["measured_values"]["stop"] == stop_a and
            right["result"]["measured_values"]["stop"] == stop_b and
            stop_a["stationary_pre_crossing_frames"] == 30 and
            stop_a["halt_before_nearest_boundary"] is True and
            stop_b["stationary_pre_crossing_frames"] == 0 and
            stop_b["halt_before_nearest_boundary"] is False and
            left["result"]["measured_values"]["turn_yield"] ==
            right["result"]["measured_values"]["turn_yield"],
            "Absent-reference measured outcome differs")
    require(all(side["result"].get("accepted") is False and
                side["result"].get("legal_verdict_claimed") is False
                for side in (left, right)), "Comparison claimed acceptance")
    return {"format": "c110919-absent-reference-saved-comparison-v1",
            "comparison_id": declaration["comparison_id"],
            "case_ids": declaration["case_ids"],
            "declared_differences": declaration["deliberate_differences"],
            "different_motion_frame_range": [min(differences), max(differences)],
            "reference_stationary_frames": 30, "contrast_stationary_frames": 0,
            "source_bindings": [{key: side[key] for key in
                                 ("source_sha256", "saved_processing_sha256",
                                  "construction_sha256")} for side in (left, right)],
            "source_comparison_passed": True, "diagnostic_fixture": diagnostic,
            "passed": False, "physical_or_legal_acceptance_claimed": False}


if __name__ == "__main__":
    print(json.dumps(compare(load("absent_reference", diagnostic=True),
                             load("absent_reference_contrast", diagnostic=True),
                             diagnostic=True), indent=2))
