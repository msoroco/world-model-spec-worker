"""Independent post-capture freight source and four-view media audit.

The default media probe performs a full FFmpeg decode. Diagnostic fixtures can
exercise the algorithm, but they cannot establish original physical visibility.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from freight_contract import SourceError, VARIANTS, audit_source_bundle, require_case_completion


ASSIGNMENT = "testing__C149555__LVMC-11-52-030-B__motor_vehicle_driver"
CAMERAS = {
    "overview": (1920, 1080),
    "approach": (1280, 720),
    "reference_corner": (1280, 720),
    "driver_reference": (1280, 720),
}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise SourceError(reason)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe_and_decode(path: Path) -> dict:
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate,nb_read_frames", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    streams = json.loads(probe.stdout).get("streams", [])
    require(len(streams) == 1, "media must have one primary video stream")
    decode = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path),
                             "-map", "0:v:0", "-f", "null", "-"],
                            capture_output=True, text=True)
    require(decode.returncode == 0, "full video decode failed")
    return streams[0]


def audit_delivery(manifest: dict, *, attempt_root: Path, media_probe=probe_and_decode) -> dict:
    case_id = manifest.get("case_id")
    require(isinstance(case_id, str) and case_id.startswith(ASSIGNMENT + "__"), "foreign delivery case")
    variant = case_id.removeprefix(ASSIGNMENT + "__")
    require(variant in VARIANTS, "unknown freight variant")
    require(manifest.get("kind") == "delivery", "source is not a delivery attempt")
    require(manifest.get("acquisition_kind") == "original_native", "diagnostic source cannot satisfy delivery audit")
    for field in ("job_id", "attempt_id", "recording_id", "native_result_sha256"):
        require(manifest.get(field), f"missing delivery identity: {field}")
    native = manifest.get("sources", {}).get("native_result", {})
    require(native.get("sha256") == manifest["native_result_sha256"], "Native result seal mismatch")
    attempt_root = attempt_root.resolve(strict=True)
    measured = audit_source_bundle(manifest, case_id=case_id, variant=variant,
                                   source_root=attempt_root, require_raw=True)
    completion = require_case_completion(measured)
    media = manifest.get("media")
    require(isinstance(media, dict) and set(media) == set(CAMERAS), "four original camera sources required")
    media_digests = {}
    for name, size in CAMERAS.items():
        ref = media[name]
        require(isinstance(ref, dict) and ref.get("path") and ref.get("sha256"), f"missing media source: {name}")
        path = (attempt_root / ref["path"]).resolve(strict=True)
        require(path.is_relative_to(attempt_root) and path.is_file(), f"media escapes attempt: {name}")
        require(sha256_file(path) == ref["sha256"], f"stale media source: {name}")
        info = media_probe(path)
        require((info.get("width"), info.get("height")) == size, f"wrong camera size: {name}")
        require(info.get("r_frame_rate") == "20/1", f"wrong camera rate: {name}")
        require(str(info.get("nb_read_frames")) == "900", f"wrong camera frame count: {name}")
        media_digests[name] = ref["sha256"]
    return {
        "format": "worker-freight-saved-delivery-audit",
        "case_id": case_id,
        "job_id": manifest["job_id"],
        "attempt_id": manifest["attempt_id"],
        "recording_id": manifest["recording_id"],
        "native_result_sha256": manifest["native_result_sha256"],
        "frames_checked": measured["frames_checked"],
        "media_sha256": media_digests,
        "source_integrity": True,
        "full_video_decode": True,
        "physical_case_completion": completion["physical_completion"],
        "actual_pixels_reviewed": False,
        "legal_conclusion": "unresolved",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--attempt", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    print(json.dumps(audit_delivery(manifest, attempt_root=args.attempt), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
