"""Independent acceptance of one sealed original CARLA alley parking capture.

Run only after Native exit and owner release. A signed human review of the
abutting access and visible blocking is required; area is never a legal cutoff.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path

from PIL import Image, ImageChops

from delivery_audit import audit as audit_original
from physical_parking import assess

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def ffprobe_frames(path):
    command = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
               "-show_entries", "stream=nb_read_frames,codec_name", "-of", "json", str(path)]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    stream = json.loads(result.stdout)["streams"][0]
    if stream.get("codec_name") != "ffv1":
        raise ValueError("original camera video is not lossless FFV1")
    subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                    "-xerror", "-i", str(path), "-map", "0:v:0", "-f", "null", "-"],
                   check=True, capture_output=True, timeout=180)
    return int(stream["nb_read_frames"])


def video_png(path, frame):
    command = ["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"select=eq(n\\,{frame})",
               "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"]
    data = subprocess.run(command, check=True, capture_output=True).stdout
    with Image.open(io.BytesIO(data)) as image:
        return image.convert("RGB")


def audit(attempt: Path, case_id: str, review: Path) -> dict:
    root = Path(attempt)
    if not (root / "capture-seal.json").is_file():
        raise ValueError("sealed original Native capture required")
    seal = read(root / "capture-seal.json")
    if seal.get("format") != "worker-sealed-capture" or seal.get("diagnostic_fixture") is not False:
        raise ValueError("sealed original Native capture required")
    if seal.get("events") != ["capture_finished", "encoders_closed", "restoration_verified"] or seal.get("frames") != 900:
        raise ValueError("Native capture closure or frame count incomplete")
    if read(root / "native-exit.json").get("capture_seal_sha256") != sha(root / "capture-seal.json"):
        raise ValueError("Native exit does not bind sealed original")
    owner = read(root / "owner-release.json")
    if owner.get("event") != "owner_released" or owner.get("operator_attested") is not True or owner.get("native_exit_sha256") != sha(root / "native-exit.json"):
        raise ValueError("Native owner release missing")
    for name, digest in seal["sources"].items():
        if sha(root / name) != digest:
            raise ValueError("sealed source changed: " + name)
    source = root / "original-attempt"
    measured = audit_original(source, case_id)
    inventory = read(source / "inventory.json")
    measurement = {"max_access_intrusion_area_m2": measured["max_access_intrusion_area_m2"]}
    physical = assess(root, read(root / "config.json"), measurement)
    if physical["physical_checks"]["maneuver"]["status"] != "met":
        raise ValueError("original stop, park, hold and departure not physically completed")
    joined = read(source / "frame_map.json")["frames"]
    sampled = (0, 100, 450, 899)
    for camera in CAMERAS:
        video = root / (camera + ".mkv")
        if ffprobe_frames(video) != 900:
            raise ValueError("full original video decode missing: " + camera)
        with zipfile.ZipFile(source / (camera + ".zip")) as archive:
            for index in sampled:
                member = f"{index:04d}-{joined[index]['frame']}.png"
                with Image.open(io.BytesIO(archive.read(member))) as original:
                    if ImageChops.difference(original.convert("RGB"), video_png(video, index)).getbbox():
                        raise ValueError("original pixel/video frame differs: " + camera)
    reviewed = read(review)
    if (reviewed.get("case_id") != case_id or reviewed.get("capture_seal_sha256") != sha(root / "capture-seal.json")
            or reviewed.get("source_inventory_sha256") != sha(source / "inventory.json")
            or reviewed.get("reviewer") in (None, "") or reviewed.get("abutting_access_confirmed") is not True
            or reviewed.get("alley_qualifies_confirmed") is not True
            or reviewed.get("actual_blocking_judgment") not in ("blocked", "not_blocked")):
        raise ValueError("independent source and pixel review missing")
    return {"format": "c229404-production-delivery-audit-v1", "case_id": case_id,
            "capture_seal_sha256": sha(root / "capture-seal.json"),
            "review_sha256": sha(review), "original_frames": 900,
            "full_lossless_video_decodes": 4, "pixel_join_sampled_frames_per_camera": list(sampled),
            "physical_status": "met", "actual_blocking_judgment": reviewed["actual_blocking_judgment"],
            "max_access_intrusion_area_m2": measured["max_access_intrusion_area_m2"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case, args.review), sort_keys=True))


if __name__ == "__main__":
    main()
