"""Independent saved Native source and physical-completion audit.

CPU diagnostic mode proves rejection/joins only. It never promotes a fixture or
converts API beam bits into legal or physical glare findings.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from beam_measure import measure as measure_motion
from beam_pixels import measure as measure_pixels

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def _source(root: Path, name: str, *, negative_remove=None) -> Path:
    if name == negative_remove:
        raise ValueError("Missing required source: " + name)
    if name != Path(name).name or name in ("", ".", ".."):
        raise ValueError("original source path must be attempt-relative")
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x]


def _decode_frames(path: Path) -> int:
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
                            "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames",
                            "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                           capture_output=True, text=True, check=True)
    try:
        frames = int(probe.stdout.strip())
    except ValueError as error:
        raise ValueError("original video frame count unavailable") from error
    decoded = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"],
                             capture_output=True, text=True)
    if decoded.returncode:
        raise ValueError("full original video decode failed: " + path.name)
    return frames


def audit(attempt: Path, case_id: str, *, diagnostic: bool = False,
          negative_remove: str | None = None, expected_frames: int = 900) -> dict:
    root = Path(attempt).resolve(strict=True)
    config = json.loads(_source(root, "config.json", negative_remove=negative_remove).read_text())
    if config.get("selected_case_id") != case_id:
        raise ValueError("saved exact beam case differs")
    case = config.get("case_plan")
    if not isinstance(case, dict) or case.get("case_id") != case_id:
        raise ValueError("saved exact case plan missing")
    receipt = json.loads(_source(root, "native-source-receipt.json", negative_remove=negative_remove).read_text())
    if receipt.get("case_id") != case_id or receipt.get("frame_count") != expected_frames:
        raise ValueError("Native beam receipt case/frame differs")
    pixel_ext = ".mkv" if "approach.mkv" in receipt.get("pixel_source_hashes", {}) else ".zip"
    names = ("site-packet.json", "actor-state.jsonl", "camera-frame-map.jsonl",
             "roi-frames.jsonl", "video_frames.jsonl", "trace.jsonl",
             "approach" + pixel_ext, "driver_reference" + pixel_ext)
    sources = {name: _hash(_source(root, name, negative_remove=negative_remove)) for name in names}
    if any(sources[name] != receipt.get("source_hashes", {}).get(name)
           for name in ("site-packet.json", "actor-state.jsonl", "camera-frame-map.jsonl")):
        raise ValueError("original Native beam source hash differs")
    if any(sources[name] != receipt.get("pixel_source_hashes", {}).get(name)
           for name in ("roi-frames.jsonl", "camera-frame-map.jsonl", "approach" + pixel_ext, "driver_reference" + pixel_ext)):
        raise ValueError("original beam pixel source hash differs")
    if not diagnostic:
        provenance = json.loads(_source(root, "acquisition-provenance.json").read_text())
        seal = json.loads(_source(root, "capture-seal.json").read_text())
        if provenance.get("provenance_kind") != "native" or seal.get("provenance_kind") != "native":
            raise ValueError("sealed Native provenance required")
        for name, digest in seal.get("sources", {}).items():
            if _hash(_source(root, name)) != digest:
                raise ValueError("sealed original source changed: " + name)
    motion = measure_motion(root, receipt["source_hashes"], expected_frames=expected_frames, case=case)
    pixels = measure_pixels(root, receipt["pixel_source_hashes"], expected_frames=expected_frames,
                            diagnostic=diagnostic, include_eye=case["branch"] == "oncoming")
    if [row["original_frame"] for row in motion["rows"]] != [row["original_frame"] for row in pixels["rows"]]:
        raise ValueError("original body and pixel frame identities differ")
    states = _rows(root / "actor-state.jsonl")
    frames = _rows(root / "video_frames.jsonl")
    trace = _rows(root / "trace.jsonl")
    if any(len(rows) != expected_frames for rows in (states, frames, trace)):
        raise ValueError("all original participant/video/trace frames required")
    for index, (state, frame, point) in enumerate(zip(states, frames, trace)):
        if (frame.get("video_frame") != index or frame.get("carla_frame") != state.get("frame") or
                point.get("frame") != state.get("frame") or
                abs(float(frame.get("time_s", -1)) - float(state["time_s"])) > 1e-4 or
                abs(float(point.get("time_s", -1)) - float(state["time_s"])) > 1e-4):
            raise ValueError("original Native/video/trace time join differs")
    media = receipt.get("camera_movies")
    if not isinstance(media, dict) or set(media) != set(VIEWS):
        raise ValueError("four original beam movies required")
    decoded = {}
    for view in VIEWS:
        item = media[view]
        path = _source(root, view + ".mkv", negative_remove=negative_remove)
        if item.get("path") != path.name or item.get("sha256") != _hash(path):
            raise ValueError("original beam movie hash differs: " + view)
        decoded[view] = _decode_frames(path)
        if decoded[view] != expected_frames or item.get("source_frame_count") != expected_frames:
            raise ValueError("full original beam video frame count differs: " + view)
    physical = "unverified"
    if not diagnostic:
        result = json.loads(_source(root, "result.json").read_text())
        checks = result.get("physical_checks", {})
        if result.get("case_id") != case_id or not isinstance(checks, dict):
            raise ValueError("source-bound physical completion result required")
        physical = checks.get("maneuver", {}).get("status", "unverified")
        if physical != "met":
            raise ValueError("original motion physical completion not met")
    return {"format": "worker-delivery-audit", "case_id": case_id,
            "diagnostic_fixture": diagnostic,
            "checks": {"native_source": not diagnostic, "all_participants": True,
                       "time_join": True, "full_video_decode": True,
                       "actual_pixels": True, "physical_completion": physical},
            "original_source_hashes": sources, "decoded_frames": decoded,
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    parser.add_argument("--negative-remove-source")
    args = parser.parse_args()
    result = audit(Path(args.attempt), args.case,
                   diagnostic=args.diagnostic_fixture,
                   negative_remove=args.negative_remove_source,
                   expected_frames=(json.loads((Path(args.attempt) / "native-source-receipt.json").read_text())["frame_count"]
                                    if args.diagnostic_fixture else 900))
    output = Path(args.output)
    if output.exists():
        raise ValueError("independent audit output already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"case_id": args.case, "passed": True,
                      "diagnostic_fixture": args.diagnostic_fixture}))


if __name__ == "__main__":
    main()
