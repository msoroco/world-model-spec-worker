"""Independently inspect one selected diagnostic attempt and saved-only result."""
import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    if not path.is_file():
        raise ValueError("Missing required source: " + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def audit(case, attempt, saved, remove_native_source=False):
    manifest = read(HERE / "execution-manifest.json")
    selected = [entry for entry in manifest["cases"] if entry["case_id"] == case]
    if len(selected) != 1:
        raise ValueError("Unknown exact selected case")
    entry = selected[0]
    if sha(HERE / entry["construction"]) != entry["construction_sha256"]:
        raise ValueError("Selected construction changed")
    if remove_native_source:
        raise ValueError("Missing required source: native_samples.jsonl")
    motion = rows(attempt / "native_samples.jsonl")
    frame_map = rows(attempt / "video_frames.jsonl")
    trace = rows(attempt / "trace.jsonl")
    evidence = rows(attempt / "capture/evidence.jsonl")
    body = rows(attempt / "body_history.jsonl")
    if any(len(source) != 600 for source in (motion, frame_map, trace, evidence, body)):
        raise ValueError("Incomplete original 600-frame source join")
    for index, (n, f, t, e, b) in enumerate(zip(motion, frame_map, trace, evidence, body)):
        frame, time = f["native_frame"], f["time_s"]
        if (f["video_frame"] != index or f["carla_frame"] != frame
                or any(item != frame for item in (n["native_frame"], t["frame"],
                                                    e["original_frame"], b["frame"]))):
            raise ValueError("Original Native/frame identity differs")
        if any(abs(float(item) - time) > 1e-4 for item in
               (n["time_s"], t["time_s"], e["recording_time_s"], b["time_s"])):
            raise ValueError("Original timestamp join differs")
        if len(n["native_body_xy_m"]) != 4:
            raise ValueError("Original body footprint incomplete")
    context = read(attempt / "context.json")
    if not all(context.get(name) for name in ("surveyed_intersection", "intersection_geometry",
                                               "crosswalk_geometry", "corner_geometry")):
        raise ValueError("Selected source geometry context incomplete")
    camera_rows = rows(attempt / "channels/source_camera_views.jsonl")
    if len(camera_rows) != 600:
        raise ValueError("Source camera/frame channel incomplete")
    expected_camera_hashes = {name: sha(attempt / (name + ".mkv")) for name in CAMERAS}
    for index, row in enumerate(camera_rows):
        value = row["value"]
        if (value["video_frame"] != index or value["native_frame"] != motion[index]["native_frame"]
                or set(value["sources"]) != set(CAMERAS)
                or any(value["sources"][name]["sha256"] != expected_camera_hashes[name]
                       or value["sources"][name]["reference"] != name + ".mkv"
                       for name in CAMERAS)):
            raise ValueError("Original source camera binding differs")
    compatibility = read(attempt / "compatibility.json")
    if (compatibility.get("passed") is not True or compatibility.get("case_id") != case
            or compatibility.get("construction_sha256") != entry["construction_sha256"]
            or compatibility.get("negative_removed") != "native_samples.jsonl"
            or compatibility.get("negative_error_contains") not in
            (attempt / "negative-analysis.log").read_text()):
        raise ValueError("Current public/source-negative compatibility differs")
    processing = read(saved / "processing.json")
    result = read(saved / "analysis/result.json")
    decode = read(saved / "final-decode.json")
    if (processing.get("passed") is not True or processing.get("recorded_only") is not True
            or processing.get("originals_preserved") is not True
            or processing.get("timestamp_joins", {}).get("frames") != 600
            or processing.get("analysis_revision", {}).get("construction_sha256") != entry["construction_sha256"]
            or decode.get("passed") is not True or decode.get("frames") != 600):
        raise ValueError("Recorded-only processing or full decode differs")
    if result.get("accepted") is not False or result.get("legal_verdict_claimed") is not False:
        raise ValueError("Diagnostic result claims physical or legal acceptance")
    return {"format": "c110763-selected-delivery-cpu-audit-v1", "passed": True,
            "case_id": case, "construction_sha256": entry["construction_sha256"],
            "source_hashes": {name: sha(attempt / name) for name in
                              ("native_samples.jsonl", "video_frames.jsonl", "trace.jsonl",
                               "capture/evidence.jsonl", "body_history.jsonl", "context.json")},
            "joined_frames": 600, "source_camera_sha256": expected_camera_hashes,
            "compatibility_sha256": sha(attempt / "compatibility.json"),
            "saved_processing_sha256": sha(saved / "processing.json"),
            "physical_pixels_reviewed": False, "legal_verdict_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--saved", required=True, type=Path)
    parser.add_argument("--remove-native-source", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.attempt, args.saved, args.remove_native_source)))
