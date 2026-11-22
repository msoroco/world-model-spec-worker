"""Independently verify retained diagnostic sources for selected C111256 chains."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SIZES = {"overview": [1920, 1080], "approach": [1280, 720],
         "reference_corner": [1280, 720], "driver_reference": [1280, 720]}
SOURCES = ("native_samples.jsonl", "video_frames.jsonl", "capture/evidence.jsonl",
           "road_geometry.json", "road.xodr", *[name + ".mkv" for name in CAMERAS])

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text())

def require(value, reason):
    if not value:
        raise ValueError(reason)

def audit(attempt, saved, entry, candidate):
    construction = entry if candidate == "primary" else next(
        c for c in entry["candidates"] if c["id"] == candidate)
    selection = read(attempt / "candidate-selection.json")
    receipt = read(attempt / "four-view-receipt.json")
    provenance = read(attempt / "acquisition-provenance.json")
    processing = read(saved)
    require(selection["case_id"] == entry["case_id"] and
            selection["candidate_id"] == candidate and
            selection["construction_sha256"] == construction["construction_sha256"],
            "Selected construction differs")
    require(provenance == {"provenance_kind": "synthetic_fixture",
                           "diagnostic_fixture": True},
            "Diagnostic provenance differs")
    require(processing["case_id"] == entry["case_id"] and
            processing["candidate_id"] == candidate and
            processing["passed"] is True and processing["recorded_only"] is True and
            processing["originals_preserved"] is True and
            processing["native_revision"]["construction_sha256"] ==
            construction["construction_sha256"], "Saved source binding differs")
    hashes = {name: sha(attempt / name) for name in SOURCES}
    require(all(processing["original_source_hashes"].get(name) == value
                for name, value in hashes.items()), "Retained source hash differs")
    require(receipt["format"] == "synchronized-four-view" and
            receipt["frames"] == 480 and
            receipt["frame_map_sha256"] == hashes["video_frames.jsonl"] and
            receipt["primary_sha256"] == sha(attempt / "raw.mkv") and
            set(receipt["sources"]) == set(CAMERAS) and
            all(receipt["sources"][name] == hashes[name + ".mkv"] for name in CAMERAS),
            "Four-view source binding differs")
    source_frames = (attempt / "native_samples.jsonl").read_text().splitlines()
    frame_map = (attempt / "video_frames.jsonl").read_text().splitlines()
    evidence = (attempt / "capture/evidence.jsonl").read_text().splitlines()
    require(len(source_frames) == len(frame_map) == len(evidence) == 480,
            "Source frame interval differs")
    for index, (a, b, c) in enumerate(zip(source_frames, frame_map, evidence)):
        sample, frame, event = json.loads(a), json.loads(b), json.loads(c)
        require(event.get("synthetic_diagnostic") is True and
                sample.get("speed_provenance") == "synthetic_native_sample" and
                sample.get("native_frame") == frame.get("native_frame") ==
                event.get("original_frame") and frame.get("video_frame") == index,
                "Source frame or synthetic speed differs")
    cameras = {}
    for name in CAMERAS:
        path = attempt / (name + ".mkv")
        probe = json.loads(subprocess.check_output([
            "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,nb_read_frames",
            "-of", "json", str(path)], text=True))["streams"][0]
        require([probe.get("width"), probe.get("height")] == SIZES[name] and
                probe.get("r_frame_rate") == "20/1" and
                int(probe.get("nb_read_frames", -1)) == 480,
                "Four-view camera frame or dimension differs: " + name)
        cameras[name] = {"sha256": hashes[name + ".mkv"], "frames": 480,
                         "dimensions": SIZES[name]}
    require(not (attempt / "capture-seal.json").is_file() and
            not (attempt / "owner-release.json").is_file(),
            "Synthetic fixture unexpectedly has Native release")
    return {"format": "c111256-current-source-audit-v1",
            "case_id": entry["case_id"], "candidate_id": candidate,
            "construction_sha256": construction["construction_sha256"],
            "saved_processing_sha256": sha(saved), "source_sha256": hashes,
            "camera_sources": cameras, "source_join_frames": 480,
            "diagnostic_fixture": True, "camera_source_shape_passed": True,
            "original_native_acceptance_rejected": True, "passed": False,
            "delivery_accepted": False}

def main():
    manifest = HERE / "current-runtime-reproof-manifest.json"
    entries = read(manifest)["cases"]
    attempt_root = ROOT / ".runtime-work"
    attempts = {}
    for path in attempt_root.glob("c111256-current-*-compat"):
        receipt = path / "compatibility.json"
        if receipt.is_file():
            attempts[sha(receipt)] = path
    rows = []
    selected = set(os.environ.get("C111256_CASE_FILTER", "").split(",")) - {""}
    candidates = set(os.environ.get("C111256_CANDIDATE_FILTER", "").split(",")) - {""}
    for entry in entries:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        if selected and suffix not in selected:
            continue
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            if candidates and candidate not in candidates:
                continue
            folder = HERE / "current-runtime-selected-proof" / suffix / candidate
            receipt, saved = folder / "compatibility.json", folder / "saved-processing.json"
            require(receipt.is_file() and saved.is_file(),
                    "Current compatibility/saved receipt missing: " + suffix + "/" + candidate)
            attempt = attempts.get(sha(receipt))
            require(attempt is not None, "Retained current attempt missing")
            output = audit(attempt, saved, entry, candidate)
            path = folder / "source-camera-audit.json"
            path.write_text(json.dumps(output, indent=2) + "\n")
            rows.append({"case_id": entry["case_id"], "candidate_id": candidate,
                         "receipt": str(path.relative_to(HERE)), "sha256": sha(path)})
            print(suffix, candidate, "diagnostic camera source passed", flush=True)
    if not selected and not candidates:
        require(len(rows) == 24, "Twenty-four source audits required")
        output = HERE / "current-runtime-selected-source-audit.json"
        output.write_text(json.dumps({
            "format": "c111256-current-source-audit-index-v1",
            "manifest_sha256": sha(manifest), "candidate_count": len(rows),
            "rows": rows, "original_native_or_delivery_acceptance_claimed": False
        }, indent=2) + "\n")

if __name__ == "__main__":
    main()
