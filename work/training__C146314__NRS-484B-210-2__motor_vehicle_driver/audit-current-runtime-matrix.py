"""Independent retained-source, four-camera, and receipt audit for eight right-pass chains."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCES = ("native-raw-actors.jsonl", "video_frames.jsonl", "trace.jsonl",
           "capture/manifest.json", "capture/evidence.jsonl",
           "capture/native/frames.jsonl", "road.xodr", *(name + ".mkv" for name in CAMERAS))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit(entry, candidate, expected):
    case = entry["case_id"]
    suffix = case.removeprefix(HERE.name + "__")
    folder = HERE / "current-runtime-selected-proof" / suffix / candidate
    attempt = (ROOT / ".runtime-work/c146314-current-matrix" / suffix / candidate / "compat")
    saved = read(folder / "saved-processing.json")
    compat = read(folder / "compatibility.json")
    selection = read(attempt / "candidate-selection.json")
    provenance = read(attempt / "acquisition-provenance.json")
    require(selection["case_id"] == case and selection["candidate_id"] == candidate and
            selection["construction_sha256"] == expected["construction_sha256"] and
            compat["passed"] is True and compat["construction_sha256"] == expected["construction_sha256"] and
            saved["passed"] is True and saved["recorded_only"] is True and
            saved["originals_preserved"] is True and saved["timestamp_joins"]["passed"] is True and
            saved["physical_acceptance_claimed"] is False and saved["legal_acceptance_claimed"] is False and
            provenance.get("provenance_kind") == "synthetic_fixture" and
            provenance.get("diagnostic_fixture") is True and
            provenance.get("native_executed") is False,
            "Selected source or provenance differs")
    hashes = {name: sha(attempt / name) for name in SOURCES}
    require(all(saved["original_source_hashes"].get(name) == value for name, value in hashes.items()),
            "Saved original source hash differs")
    receipt = read(attempt / "four-view-receipt.json")
    require(receipt["format"] == "synchronized-four-view" and receipt["frames"] == 240 and
            receipt["frame_map_sha256"] == hashes["video_frames.jsonl"] and
            all(receipt["sources"][name] == hashes[name + ".mkv"] for name in CAMERAS),
            "Four-view source receipt differs")
    samples = [json.loads(line) for line in (attempt / "native-raw-actors.jsonl").read_text().splitlines()]
    frames = [json.loads(line) for line in (attempt / "video_frames.jsonl").read_text().splitlines()]
    require(len(samples) == len(frames) == 240 and all(
        sample["native_frame"] == frame["native_frame"] and sample["frame"] == i and sample["time_s"] == frame["time_s"] and frame["synthetic_frame_only"] is True and frame["video_frame"] == i and
        sample.get("source_kind") == "synthetic_native_sample"
        for i, (sample, frame) in enumerate(zip(samples, frames))),
        "Native/video frame join or synthetic provenance differs")
    cameras = {}
    for name in CAMERAS:
        video = attempt / (name + ".mkv")
        probe = json.loads(subprocess.check_output([
            "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,nb_read_frames",
            "-of", "json", str(video)], text=True))["streams"][0]
        size = [1920, 1080] if name == "overview" else [1280, 720]
        require([probe["width"], probe["height"]] == size and
                probe["r_frame_rate"] == "20/1" and int(probe["nb_read_frames"]) == 240,
                "Camera source shape differs: " + name)
        cameras[name] = {"sha256": hashes[name + ".mkv"], "frames": 240,
                         "dimensions": size}
    require(not (attempt / "capture-seal.json").exists() and
            not (attempt / "owner-release.json").exists(),
            "Synthetic attempt has original release")
    output = {"format": "c146314-current-source-audit-v1", "case_id": case,
              "candidate_id": candidate, "construction_sha256": expected["construction_sha256"],
              "saved_processing_sha256": sha(folder / "saved-processing.json"),
              "source_sha256": hashes, "cameras": cameras, "joined_frames": 240,
              "original_native_accepted": False}
    path = folder / "source-camera-audit.json"
    path.write_text(json.dumps(output, indent=2) + "\n")
    return {"case_id": case, "candidate_id": candidate,
            "receipt": str(path.relative_to(HERE)), "sha256": sha(path)}


def main():
    manifest_path = HERE / "current-runtime-reproof-manifest.json"
    manifest = read(manifest_path)
    rows = []
    for entry in manifest["cases"]:
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            selected = entry if candidate == "primary" else next(
                row for row in entry["candidates"] if row["id"] == candidate)
            rows.append(audit(entry, candidate, selected))
            print(entry["case_id"].rsplit("__", 1)[-1], candidate, "source passed", flush=True)
    require(len(rows) == 8, "Eight source audits required")
    output = HERE / "current-runtime-selected-source-audit.json"
    output.write_text(json.dumps({"format": "c146314-current-source-index-v1",
                                  "manifest_sha256": sha(manifest_path), "rows": rows,
                                  "original_native_accepted": False}, indent=2) + "\n")
    print(json.dumps({"candidate_count": len(rows), "index_sha256": sha(output)}))


if __name__ == "__main__":
    main()
