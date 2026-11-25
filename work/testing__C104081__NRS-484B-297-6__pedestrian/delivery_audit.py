"""Independent saved-source audit for the exact pedestrian bypass cases.

This verifies acquisition identity, original frame continuity, measurements and
sealed camera bytes. It deliberately leaves pixel visibility and physical/legal
completion unresolved; a metadata or diagnostic fixture is not acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from saved_measurement import measure_saved

ASSIGNMENT = "testing__C104081__NRS-484B-297-6__pedestrian"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
EXPECTED_FRAMES = 900
EXPECTED_DIMENSIONS = {
    "overview": (1920, 1080),
    "approach": (1280, 720),
    "reference_corner": (1280, 720),
    "driver_reference": (1280, 720),
}
CASE_EXPECTATIONS = {
    "clear_intervening": (1, False, False, 34.0, "impassable_section"),
    "blocked_intervening": (1, True, True, 34.0, "impassable_section"),
    "blocked_opposite": (-1, True, True, 34.0, "impassable_section"),
    "blocked_late_return": (1, True, True, 40.0, "impassable_section"),
    "missing_sidewalk": (1, False, False, 34.0, "missing_section"),
}


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _local_file(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("media path must be relative to saved attempt")
    root = root.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError("media path escapes saved attempt")
    if not path.is_file():
        raise ValueError("missing sealed camera file")
    return path


def _decode_media(path: Path, camera: str, *, diagnostic: bool) -> dict:
    """Count and fully decode one sealed camera video with installed CPU tools."""
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
         "-show_entries", "stream=width,height,r_frame_rate,nb_read_frames",
         "-of", "json", str(path)], capture_output=True, text=True, check=False,
    )
    if probe.returncode:
        raise ValueError(f"camera probe failed: {camera}: {probe.stderr.strip()[:200]}")
    try:
        streams = json.loads(probe.stdout)["streams"]
        if len(streams) != 1:
            raise ValueError("multiple selected video streams")
        stream = streams[0]
        count = int(stream["nb_read_frames"])
        width, height = int(stream["width"]), int(stream["height"])
        rate = stream["r_frame_rate"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError(f"camera probe lacks complete video metadata: {camera}") from exc
    if count != EXPECTED_FRAMES or rate != "20/1":
        raise ValueError(f"decoded camera frame count or cadence mismatch: {camera}")
    if (width, height) != EXPECTED_DIMENSIONS[camera] and not diagnostic:
        raise ValueError(f"camera dimensions differ from capture profile: {camera}")
    decoded = subprocess.run(
        ["ffmpeg", "-v", "error", "-xerror", "-i", str(path),
         "-map", "0:v:0", "-f", "null", "-"],
        capture_output=True, text=True, check=False,
    )
    if decoded.returncode:
        raise ValueError(f"full camera decode failed: {camera}: {decoded.stderr.strip()[:200]}")
    return {"frame_count": count, "fps": 20, "width": width, "height": height,
            "profile_dimensions": (width, height) == EXPECTED_DIMENSIONS[camera]}


def audit_saved(root: Path, case_id: str, *, diagnostic: bool = False,
                decode_media: bool = False) -> dict:
    """Validate original-shaped saved sources; fixtures require explicit opt-in."""
    if not case_id.startswith(ASSIGNMENT + "__") or case_id[len(ASSIGNMENT) + 2:] not in CASE_EXPECTATIONS:
        raise ValueError("unknown exact pedestrian case")
    root = Path(root)
    packet_path = root / "source-packet.json"
    packet = json.loads(packet_path.read_text())
    if packet.get("case_id") != case_id:
        raise ValueError("saved source exact case mismatch")
    if packet.get("source_kind") != "original_saved_acquisition" and not diagnostic:
        raise ValueError("delivery requires original saved acquisition")
    measured = measure_saved(root, case_id)
    values = measured["observables"]
    actual_case = (
        values["pedestrian_direction"], values["intervening_barrier_present"],
        values["designated_lane_used"], values["sidewalk_obstruction_end_m"],
        values["sidewalk_obstruction_kind"],
    )
    if actual_case != CASE_EXPECTATIONS[case_id[len(ASSIGNMENT) + 2:]]:
        raise ValueError("measured bypass does not match exact planned case")
    if measured["sample_count"] != EXPECTED_FRAMES:
        raise ValueError("saved attempt lacks complete 900-frame history")
    rows = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines() if line.strip()]
    if rows[-1]["carla_frame"] - rows[0]["carla_frame"] != EXPECTED_FRAMES - 1:
        raise ValueError("saved attempt skips original CARLA frames")
    if rows[-1]["video_frame"] != EXPECTED_FRAMES - 1:
        raise ValueError("saved attempt lacks final video frame")
    media = packet.get("camera_media")
    if not isinstance(media, dict) or set(media) != set(CAMERAS):
        raise ValueError("missing exact four-camera media binding")
    sealed = {}
    decoded_media = {}
    used_paths = set()
    for camera in CAMERAS:
        binding = media[camera]
        if not isinstance(binding, dict):
            raise ValueError("invalid camera media binding")
        relative = binding.get("path")
        path = _local_file(root, relative)
        if path in used_paths:
            raise ValueError("camera bindings reuse a media file")
        used_paths.add(path)
        digest = _digest(path)
        if digest != binding.get("sha256"):
            raise ValueError("camera media digest mismatch")
        if path.stat().st_size <= 0:
            raise ValueError("empty camera media")
        if binding.get("frame_count") != EXPECTED_FRAMES or binding.get("fps") != 20:
            raise ValueError("camera frame count or cadence differs from capture plan")
        sealed[camera] = {"path": relative, "sha256": digest}
        if decode_media:
            decoded_media[camera] = _decode_media(path, camera, diagnostic=diagnostic)
    return {
        "format": "worker-pedestrian-bypass-saved-source-audit",
        "case_id": case_id,
        "source_kind": packet["source_kind"],
        "source_packet_sha256": _digest(packet_path),
        "source_integrity": "passed",
        "measured_observables": measured["observables"],
        "original_frame_count": EXPECTED_FRAMES,
        "sealed_camera_media": sealed,
        "decoded_camera_media": decoded_media,
        "checks": {
            "native_source": packet["source_kind"] == "original_saved_acquisition",
            "all_participants": False,
            "time_join": True,
            "full_video_decode": decode_media,
            "actual_pixels": False,
            "physical_completion": False,
        },
        "legal_judgment": "unresolved",
        "physical_acceptance": "not_assessed",
    }


def audit_delivery(root: Path, case_id: str, review_path: Path) -> dict:
    """Require independent original-pixel review and sealed physical completion."""
    from original_review import audit_original_review
    source = audit_saved(root, case_id, decode_media=True)
    reviewed = audit_original_review(root, case_id, source, review_path)
    source["checks"] = reviewed["checks"]
    source["independent_review"] = {
        "pixel_review_sha256": reviewed["pixel_review_sha256"],
        "participant_census": reviewed["participant_census"],
    }
    source["physical_acceptance"] = "source_reviewed_pending_canonical_acceptance"
    return source


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit exact saved pedestrian bypass sources")
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--case", required=True)
    parser.add_argument("--decode-media", action="store_true")
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--review", type=Path,
                        help="independent original-pixel review after Native owner release")
    args = parser.parse_args()
    if args.review:
        if args.diagnostic:
            raise ValueError("diagnostic fixture cannot enter original pixel review")
        receipt = audit_delivery(args.attempt, args.case, args.review)
    else:
        receipt = audit_saved(args.attempt, args.case, diagnostic=args.diagnostic,
                              decode_media=args.decode_media)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
