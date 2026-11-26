"""Independent original-history and four-camera delivery preparation audit.

Passing source checks does not establish elevator visibility or legal meaning;
those require original pixel review and physical observation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from parking import CASES
from reviewed_site import verify
from saved_audit import audit_original_history


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SIZES = ((1920, 1080), (1280, 720), (1280, 720), (1280, 720))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _decode(path: Path, name: str) -> int:
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                            "-show_entries", "stream=nb_read_frames,r_frame_rate,width,height",
                            "-of", "json", str(path)], capture_output=True, text=True, timeout=90)
    try:
        streams = json.loads(probe.stdout)["streams"]
        if len(streams) != 1:
            raise ValueError
        stream = streams[0]
        frames = int(stream["nb_read_frames"])
    except (ValueError, KeyError, TypeError, IndexError):
        raise ValueError("original camera frame probe failed: " + name) from None
    if probe.returncode or frames != 900:
        raise ValueError("original camera frame count differs: " + name)
    if (stream.get("r_frame_rate") not in ("20", "20/1") or
            (stream.get("width"), stream.get("height")) != SIZES[CAMERAS.index(name)]):
        raise ValueError("original camera profile differs: " + name)
    decode = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path),
                             "-f", "null", "-"], capture_output=True, text=True, timeout=180)
    if decode.returncode or decode.stderr.strip():
        raise ValueError("original camera full decode failed: " + name)
    return frames


def audit(attempt: Path, packet_path: Path, source_root: Path, *,
          diagnostic_fixture: bool = False, decoder=None) -> dict:
    attempt = Path(attempt)
    packet = verify(packet_path, source_root)
    site_sha = _sha(Path(packet_path))
    seal = json.loads((attempt / "capture-seal.json").read_text())
    case_id = seal.get("case_id", "")
    prefix = packet["assignment_id"] + "__"
    if not case_id.startswith(prefix) or case_id[len(prefix):] not in {item.id for item in CASES}:
        raise ValueError("sealed exact case differs from reviewed packet")
    if (seal.get("format") != "sidewalk-elevator-native-seal" or
            seal.get("site_packet_sha256") != site_sha or seal.get("frames") != 900 or
            seal.get("capture_rate_hz") != 20 or seal.get("owner_released") is not True or
            seal.get("restoration_verified") is not True or
            seal.get("native_process_exit_code") != 0 or
            any(seal.get("encoder_exit_codes", {}).get(name) != 0 for name in CAMERAS)):
        raise ValueError("original capture identity or owner release incomplete")
    if diagnostic_fixture:
        if seal.get("provenance_kind") != "synthetic_fixture":
            raise ValueError("diagnostic seal provenance mismatch")
    elif seal.get("provenance_kind") != "original_native" or decoder is not None:
        raise ValueError("original Native capture and full decoder required")
    hashes = seal.get("sources", {})
    required = ("history.jsonl", "camera-frame-map.jsonl", *(name + ".mkv" for name in CAMERAS))
    for name in required:
        path = attempt / name
        if not path.is_file() or hashes.get(name) != _sha(path):
            raise ValueError("sealed original source missing or changed: " + name)
    history = audit_original_history(attempt / "history.jsonl", hashes["history.jsonl"],
                                     case_id[len(prefix):], site_sha)
    mapping = [json.loads(line) for line in (attempt / "camera-frame-map.jsonl").read_text().splitlines()]
    rows = [json.loads(line) for line in (attempt / "history.jsonl").read_text().splitlines()]
    if len(mapping) != 900 or len(rows) != 900:
        raise ValueError("original camera/history frame count differs")
    for index, (frame, row) in enumerate(zip(mapping, rows)):
        if (frame.get("original_frame") != row.get("original_frame") or
                frame.get("time_s") != row.get("time_s") or
                frame.get("camera_frames") != {name: index for name in CAMERAS}):
            raise ValueError("original camera frame/time join differs")
    for name in CAMERAS:
        count = decoder(attempt / (name + ".mkv"), name) if diagnostic_fixture and decoder else (
            _decode(attempt / (name + ".mkv"), name))
        if count != 900:
            raise ValueError("original camera decode count differs: " + name)
    return {"format": "sidewalk-elevator-delivery-audit", "case_id": case_id,
            "site_packet_sha256": site_sha, "source_hashes": hashes,
            "frame_count": history["frame_count"], "camera_count": len(CAMERAS),
            "full_video_decode": True, "physical_acceptance_claimed": False,
            "legal_judgment": None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("delivery audit output already exists")
    result = audit(args.attempt, args.packet, args.source_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
