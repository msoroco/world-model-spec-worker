"""Independently audit source retention, four cameras, and selected CPU receipts."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCES = ("bus_native_rows.jsonl", "officer_signal_rows.jsonl",
           "officer_signal_definition.json", "video_frames.jsonl", "trace.jsonl",
           "capture/manifest.json", "capture/evidence.jsonl", "capture/native/frames.jsonl",
           "road.xodr", *(name + ".mkv" for name in CAMERAS))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit(entry, candidate):
    case = entry["case_id"]
    suffix = case.removeprefix(HERE.name + "__")
    selected = entry if candidate == "primary" else next(
        row for row in entry["candidates"] if row["id"] == candidate)
    folder = HERE / "current-runtime-selected-proof" / suffix / candidate
    attempt = ROOT / ".runtime-work/c177225-current-matrix" / suffix / candidate / "compat"
    saved = read(folder / "saved-processing.json")
    compat = read(folder / "compatibility.json")
    selection = read(attempt / "candidate-selection.json")
    provenance = read(attempt / "acquisition-provenance.json")
    require(selection["case_id"] == case and selection["candidate_id"] == candidate and
            selection["construction_sha256"] == selected["construction_sha256"] and
            compat["passed"] is True and compat["construction_sha256"] == selected["construction_sha256"] and
            saved["passed"] is True and saved["recorded_only"] is True and
            saved["originals_preserved"] is True and saved["timestamp_joins"]["passed"] is True and
            saved["physical_acceptance_claimed"] is False and saved["legal_acceptance_claimed"] is False and
            provenance.get("provenance_kind") == "synthetic_fixture" and
            provenance.get("diagnostic_fixture") is True and provenance.get("native_executed") is not True,
            "Selected source or provenance differs")
    hashes = {name: sha(attempt / name) for name in SOURCES}
    require(all(saved["original_source_hashes"].get(name) == digest for name, digest in hashes.items()),
            "Saved retained source differs")
    receipt = read(attempt / "four-view-receipt.json")
    count = receipt["frames"]
    require(receipt["format"] == "synchronized-four-view" and count == 600 and
            receipt["frame_map_sha256"] == hashes["video_frames.jsonl"] and
            all(receipt["sources"][name] == hashes[name + ".mkv"] for name in CAMERAS),
            "Four-view source receipt differs")
    rows = [read_row for read_row in (json.loads(line) for line in
            (attempt / "video_frames.jsonl").read_text().splitlines())]
    require(len(rows) == count and all(row["video_frame"] == index and
            row["native_frame"] == row["carla_frame"] == index + 1
            for index, row in enumerate(rows)),
            "Native/video frame join differs")
    cameras = {}
    for name in CAMERAS:
        video = attempt / (name + ".mkv")
        probe = json.loads(subprocess.check_output([
            "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,nb_read_frames",
            "-of", "json", str(video)], text=True))["streams"][0]
        size = [1920, 1080] if name == "overview" else [1280, 720]
        require([probe["width"], probe["height"]] == size and
                probe["r_frame_rate"] == "20/1" and int(probe["nb_read_frames"]) == count,
                "Camera source shape differs: " + name)
        cameras[name] = {"sha256": hashes[name + ".mkv"], "frames": count,
                         "dimensions": size}
    output = {"format": "c177225-current-source-audit-v1", "case_id": case,
              "candidate_id": candidate, "construction_sha256": selected["construction_sha256"],
              "saved_processing_sha256": sha(folder / "saved-processing.json"),
              "source_sha256": hashes, "cameras": cameras,
              "joined_frames": count, "original_native_accepted": False}
    path = folder / "source-camera-audit.json"
    path.write_text(json.dumps(output, indent=2) + "\n")
    print(suffix, candidate, "source passed", flush=True)
    return {"case_id": case, "candidate_id": candidate,
            "receipt": str(path.relative_to(HERE)), "sha256": sha(path)}


def main():
    manifest_path = HERE / "current-runtime-reproof-manifest.json"
    manifest = read(manifest_path)
    rows = [audit(entry, candidate) for entry in manifest["cases"]
            for candidate in ("primary", "fallback1", "fallback2", "fallback3")]
    require(len(rows) == 8, "Eight source audits required")
    output = HERE / "current-runtime-selected-source-audit.json"
    output.write_text(json.dumps({"format": "c177225-current-source-index-v1",
                                  "manifest_sha256": sha(manifest_path), "rows": rows,
                                  "original_native_accepted": False}, indent=2) + "\n")
    print(json.dumps({"candidate_count": len(rows), "index_sha256": sha(output)}))


if __name__ == "__main__":
    main()
