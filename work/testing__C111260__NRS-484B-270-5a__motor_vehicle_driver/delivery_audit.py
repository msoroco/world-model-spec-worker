"""Independent source and decoded-pixel audit for a saved mounted-rider attempt."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile

from PIL import Image
from io import BytesIO

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
ROLES = {"overview": "motorist and mounted rider routes",
         "approach": "motorist approach and rider class",
         "reference_corner": "rider mount, conflict window and separation",
         "driver_reference": "motorist response and surrounding encounter"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit_saved(attempt, *, case_id, packet_sha256, require_attested=False,
                video_manifest_sha256=None, pixel_review_path=None,
                pixel_review_sha256=None):
    """Recheck the original Native packet, camera archives and reviewed pixels."""
    from saved_encounter import finalize_saved
    from native_capture import audit_original_pixels
    from video_media import audit_composed
    from native_site import verify as verify_site
    root = Path(attempt).resolve()
    packet_path = root / "encounter-packet.json"
    if sha(packet_path) != packet_sha256:
        raise ValueError("encounter packet hash drift")
    packet = read(packet_path)
    if packet.get("case_id") != case_id:
        raise ValueError("exact delivery case differs")
    if require_attested:
        if packet.get("capture_origin") != "native_adapter_attested" or not packet.get("native_site"):
            raise ValueError("reviewed original Native source absent")
        verify_site(root, packet["native_site"], expected_kind=case_id.rsplit("__", 1)[-1].rsplit("_", 1)[0])
    observed = finalize_saved(root)
    pixels = audit_original_pixels(root)
    output = {"case_id": case_id, "rider_kind": observed["kind"],
              "original_frames": observed["original_frames"],
              "decoded_original_images": pixels["decoded_images"],
              "physical_completion": False, "full_video_decode": False,
              "actual_pixels": False}
    if video_manifest_sha256:
        output["full_video_decode"] = audit_composed(
            root, {"path": "video-media.json", "sha256": video_manifest_sha256})["full_video_decode"]
    if pixel_review_path is not None:
        path = Path(pixel_review_path)
        if not pixel_review_sha256 or sha(path) != pixel_review_sha256:
            raise ValueError("pixel review hash drift")
        review = read(path)
        if (review.get("format") != "c111260-independent-pixel-review-v1" or
                review.get("case_id") != case_id or
                review.get("packet_sha256") != packet_sha256 or
                review.get("video_manifest_sha256") != video_manifest_sha256 or
                review.get("original_frames") != observed["original_frames"]):
            raise ValueError("independent pixel review identity differs")
        views = review.get("views", {})
        if set(views) != set(VIEWS):
            raise ValueError("independent pixel review omits a camera")
        camera_frames = read(root / "camera-frames.json")
        for name in VIEWS:
            for item in views[name]:
                if (not item.get("ego_visible") or not item.get("rider_visible") or
                        not item.get("person_mounted_visible") or
                        item.get("rider_kind_visible") != observed["kind"]):
                    raise ValueError("independent pixel role or source differs")
                frame = item.get("frame")
                if frame not in camera_frames[name]:
                    raise ValueError("independent pixel role or source differs")
                with ZipFile(root / (name + ".png.zip")) as archive:
                    original = archive.read(f"{frame:08d}.png")
                if hashlib.sha256(original).hexdigest() != item.get("original_png_sha256"):
                    raise ValueError("independent pixel role or source differs")
                index = camera_frames[name].index(frame)
                command = ["ffmpeg", "-nostdin", "-v", "error", "-i", str(root / (name + ".mkv")),
                           "-vf", f"select=eq(n\\,{index})", "-frames:v", "1",
                           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
                encoded = subprocess.run(command, capture_output=True, check=True).stdout
                with Image.open(BytesIO(original)) as image:
                    source_rgb = image.convert("RGB").tobytes()
                if encoded != source_rgb:
                    raise ValueError("encoded pixels differ from original")
        output["actual_pixels"] = True
    return output


def audit(attempt, processing_path, case, review_path, *, diagnostic=False):
    from worker_exchange.media import audit as decode
    attempt, processing_path, review_path = map(Path, (attempt, processing_path, review_path))
    attempt = attempt.resolve()
    processing = read(processing_path)
    if (processing.get("format") != "worker-saved-processing" or
            processing.get("passed") is not True or
            processing.get("originals_preserved") is not True or
            processing.get("case_id") != case):
        raise ValueError("saved-only processing receipt missing or failed")
    for rel, digest in processing.get("original_source_hashes", {}).items():
        source = attempt / rel
        if not source.is_file() or sha(source) != digest:
            raise ValueError("saved original changed: " + rel)
    result_path = Path(processing["result"])
    if sha(result_path) != processing.get("result_sha256"):
        raise ValueError("saved result changed")
    result = read(result_path)
    if result.get("case_id") != case or result.get("diagnostic_fixture") is not diagnostic:
        raise ValueError("result identity or provenance differs")
    packet = read(attempt / "encounter-packet.json")
    if packet.get("case_id") != case or packet.get("diagnostic_fixture") is not diagnostic:
        raise ValueError("original encounter identity or provenance differs")
    for key in ("site", "history", "camera_frames"):
        ref = packet[key]
        if sha(attempt / ref["path"]) != ref["sha256"]:
            raise ValueError("source packet hash changed: " + key)
    history = read(attempt / "history.json")
    motion = rows(attempt / "trace.jsonl")
    mapping = rows(attempt / "video_frames.jsonl")
    # The saved Native row, trace row and camera frame map must share every frame.
    expected = 9 if diagnostic else 900
    if not all(len(stream) == expected for stream in (history, motion, mapping)):
        raise ValueError("original frame count incomplete")
    source_time_offset = motion[0]["time_s"] - history[0]["time_s"]
    if abs(source_time_offset) > 0.051:
        raise ValueError("original source time bases differ")
    for index, (native, trace, video) in enumerate(zip(history, motion, mapping)):
        if (native.get("frame") != trace.get("frame") or
                native.get("frame") != video.get("carla_frame") or
                abs(native.get("time_s", 1e9) + source_time_offset - trace.get("time_s", -1e9)) > 1e-5 or
                abs(trace.get("time_s", 1e9) - video.get("time_s", -1e9)) > 1e-6 or
                video.get("video_frame") != index or
                native.get("ego_actor_id") == native.get("rider_actor_id") or
                native.get("rider_person_actor_id") in
                    (native.get("ego_actor_id"), native.get("rider_actor_id")) or
                not native.get("rider_mounted_observed")):
            raise ValueError("original participant or frame join differs")
    if not diagnostic:
        seal = read(attempt / "capture-seal.json")
        exit_receipt = read(attempt / "native-exit.json")
        owner = read(attempt / "owner-release.json")
        if (seal.get("events") != ["capture_finished", "encoders_closed", "restoration_verified"] or
                seal.get("restoration", {}).get("restored") is not True or
                seal.get("diagnostic_fixture") is True or
                exit_receipt.get("capture_seal_sha256") != sha(attempt / "capture-seal.json") or
                owner.get("native_exit_sha256") != sha(attempt / "native-exit.json") or
                owner.get("operator_attested") is not True):
            raise ValueError("Native closure or owner release incomplete")
        if result.get("physical_checks", {}).get("maneuver", {}).get("status") != "met":
            raise ValueError("measured encounter traversal incomplete")
    review = read(review_path)
    if (review.get("case_id") != case or review.get("diagnostic_fixture") is not diagnostic or
            review.get("frame_map_sha256") != sha(attempt / "video_frames.jsonl") or
            set(review.get("views", {})) != set(VIEWS) or
            not review.get("reviewer") or not review.get("method")):
        raise ValueError("independent pixel review absent or stale")
    receipts = {}
    for index, name in enumerate(VIEWS):
        video = attempt / (name + ".mkv")
        receipt_path = processing_path.parent / ("source-" + str(index) + ".json")
        receipt = decode(video, expected, mapping_sha256=sha(attempt / "video_frames.jsonl"),
                         receipt=processing_path.parent / ("delivery-decode-" + name + ".json"))
        if (not receipt_path.is_file() or not receipt.get("rgb_sequence_sha256") or
                review["views"][name].get("video_sha256") != sha(video) or
                review["views"][name].get("rgb_sequence_sha256") != receipt["rgb_sequence_sha256"] or
                review["views"][name].get("required_role") != ROLES[name] or
                review["views"][name].get("visibility_status") !=
                    ("diagnostic_only" if diagnostic else "visible")):
            raise ValueError("independent original pixel review incomplete: " + name)
        receipts[name] = sha(processing_path.parent / ("delivery-decode-" + name + ".json"))
    return {"format": "c111260-independent-delivery-audit-v1", "case_id": case,
            "passed": True, "diagnostic_fixture": diagnostic,
            "checks": {"native_source": not diagnostic, "all_participants": True,
                       "time_join": True, "full_video_decode": True,
                       "actual_pixels": True, "physical_completion": not diagnostic},
            "decode_receipts": receipts, "legal_verdict": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--processing", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--pixel-review", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.processing, args.case,
                           args.pixel_review, diagnostic=args.diagnostic), indent=2))


if __name__ == "__main__":
    main()
