"""Source-bound independent review of one original pedestrian bypass attempt.

The local reviewer supplies the pixel observations after Native exit. This code
verifies the reviewed frame bytes and actor census; it does not make a legal
judgment or turn a diagnostic fixture into an original recording.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
REQUIRED_FEATURES = {
    "overview": {"entry": {"pedestrian", "sidewalk"},
                 "bypass": {"pedestrian", "obstruction", "adjacent_highway"},
                 "return": {"pedestrian", "sidewalk"}},
    "approach": {"bypass": {"pedestrian", "obstruction"}},
    "reference_corner": {"bypass": {"obstruction", "adjacent_highway"}},
    "driver_reference": {"bypass": {"adjacent_highway"}},
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> dict:
    return json.loads(path.read_text())


def _decoded_frame_hashes(path: Path, width: int, height: int,
                          frames: tuple[int, int, int]) -> dict[int, str]:
    filters = "+".join(f"eq(n\\,{frame})" for frame in frames)
    command = ["ffmpeg", "-v", "error", "-xerror", "-i", str(path),
               "-vf", f"select={filters}", "-vsync", "0", "-frames:v", "3",
               "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"]
    completed = subprocess.run(command, capture_output=True, check=False)
    frame_size = width * height * 3
    if completed.returncode or len(completed.stdout) != frame_size * 3:
        raise ValueError("reviewed original camera frames cannot be decoded")
    return {frame: hashlib.sha256(completed.stdout[index * frame_size:
                                              (index + 1) * frame_size]).hexdigest()
            for index, frame in enumerate(frames)}


def _sample_frames(saved_audit: dict, root: Path) -> tuple[int, int, int]:
    rows = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines() if line]
    if len(rows) != 900:
        raise ValueError("original pixel review lacks complete frame map")
    by_frame = {row["carla_frame"]: row["video_frame"] for row in rows}
    observed = saved_audit.get("measured_observables", {})
    highway = observed.get("highway_frames")
    returned = observed.get("first_sidewalk_return_frame")
    if not isinstance(highway, list) or not highway or returned not in by_frame:
        raise ValueError("original pixel review lacks measured bypass or return")
    frames = (0, by_frame[highway[len(highway) // 2]], by_frame[returned])
    if not 0 < frames[1] < frames[2] < 900:
        raise ValueError("original pixel review event frames are out of order")
    return frames


def _participant_census(root: Path, walker_id: int, traffic_ids: set[int]) -> dict:
    path = root / "capture/evidence.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines() if line]
    if len(rows) != 900:
        raise ValueError("original participant census lacks 900 frames")
    required = {walker_id} | traffic_ids
    for index, row in enumerate(rows):
        if row.get("original_frame") != rows[0].get("original_frame", -1) + index:
            raise ValueError("original participant census frame gap")
        observed = row.get("original_observations", {}).get("participants")
        if not isinstance(observed, list):
            raise ValueError("original participant census is missing")
        ids = [person.get("actor_id") for person in observed if isinstance(person, dict)]
        if any(type(actor_id) is not int for actor_id in ids) or len(ids) != len(set(ids)) or not required <= set(ids):
            raise ValueError("original participant census omits a required actor")
        if row.get("actor_id") != walker_id:
            raise ValueError("original pedestrian actor identity changed")
    return {"source": "capture/evidence.jsonl", "sha256": _sha(path),
            "walker_actor_id": walker_id, "traffic_actor_ids": sorted(traffic_ids),
            "frames": len(rows)}


def audit_original_review(root: Path, case_id: str, saved_audit: dict,
                          review_path: Path) -> dict:
    root = Path(root).resolve()
    if saved_audit.get("source_kind") != "original_saved_acquisition" or \
            saved_audit.get("case_id") != case_id:
        raise ValueError("original saved acquisition required for physical review")
    packet = _read(root / "source-packet.json")
    if _sha(root / "source-packet.json") != saved_audit.get("source_packet_sha256"):
        raise ValueError("review source packet seal differs")
    lifecycle = _read(root / "lifecycle-receipt.json")
    if lifecycle.get("case_id") != case_id or \
            lifecycle.get("source_packet_sha256") != saved_audit["source_packet_sha256"] or \
            lifecycle.get("world_restore", {}).get("restored") is not True:
        raise ValueError("original Native lifecycle is not sealed and restored")
    seal = _read(root / "capture-seal.json")
    context_path = root / "acquisition-context.json"
    if seal.get("format") != "worker-sealed-capture" or \
            seal.get("provenance_kind") != "native" or \
            seal.get("diagnostic_fixture") is not False or \
            seal.get("restoration", {}).get("restored") is not True or \
            seal.get("sources", {}).get("acquisition-context.json") != _sha(context_path) or \
            _read(context_path).get("source_packet_sha256") != saved_audit["source_packet_sha256"]:
        raise ValueError("original capture seal differs from source packet")
    review = _read(Path(review_path))
    if review.get("format") != "worker-pedestrian-original-pixel-review" or \
            review.get("case_id") != case_id or \
            review.get("source_packet_sha256") != saved_audit["source_packet_sha256"] or \
            not review.get("reviewer") or not review.get("method"):
        raise ValueError("independent original pixel review is absent or stale")
    roster = _read(root / "traffic-plan.json").get("actor_ids")
    walker_id = review.get("walker_actor_id")
    if type(walker_id) is not int or not isinstance(roster, list) or not roster or \
            any(type(value) is not int for value in roster) or walker_id in roster:
        raise ValueError("original pedestrian and traffic roster is invalid")
    census = _participant_census(root, walker_id, set(roster))
    frames = _sample_frames(saved_audit, root)
    cameras = review.get("cameras")
    if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS):
        raise ValueError("independent pixel review omits a camera")
    for camera in CAMERAS:
        binding = saved_audit["sealed_camera_media"][camera]
        decoded = saved_audit["decoded_camera_media"][camera]
        statement = cameras[camera]
        if statement.get("video_sha256") != binding["sha256"] or \
                not decoded.get("profile_dimensions") or decoded.get("frame_count") != 900:
            raise ValueError("independent pixel review names stale camera bytes")
        samples = statement.get("samples")
        if not isinstance(samples, list) or [item.get("frame_index") for item in samples] != list(frames):
            raise ValueError("independent pixel review lacks entry, bypass or return frames")
        video = (root / binding["path"]).resolve()
        if not video.is_relative_to(root):
            raise ValueError("reviewed video path escapes saved attempt")
        hashes = _decoded_frame_hashes(video, decoded["width"], decoded["height"], frames)
        for phase, sample in zip(("entry", "bypass", "return"), samples):
            features = sample.get("visible_features")
            if sample.get("rgb_sha256") != hashes[sample["frame_index"]] or \
                    not isinstance(features, list) or \
                    not REQUIRED_FEATURES[camera].get(phase, set()) <= set(features):
                raise ValueError("independent review lacks visible original pixels")
    result = _read(root / "result.json")
    if seal.get("sources", {}).get("result.json") != _sha(root / "result.json"):
        raise ValueError("original physical result changed after Native seal")
    if result.get("case_id") != case_id or result.get("provenance_kind") != "native" or \
            result.get("diagnostic_fixture") is not False or \
            result.get("physical_checks", {}).get("maneuver", {}).get("status") != "met" or \
            result.get("maneuver_completed") is not True:
        raise ValueError("original saved physical maneuver is not complete")
    return {"case_id": case_id, "source_packet_sha256": saved_audit["source_packet_sha256"],
            "pixel_review_sha256": _sha(Path(review_path)), "participant_census": census,
            "checks": {"native_source": True, "all_participants": True,
                       "time_join": True, "full_video_decode": True,
                       "actual_pixels": True, "physical_completion": True},
            "legal_judgment": "unresolved"}
