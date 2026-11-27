"""Independent source, frame, video and physical observation audit for a bridge case.

The diagnostic protocol self-test exercises the same joins with synthetic images
and never counts as an accepted original recording.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from bridge_observations import measure_crossing, verify_site_bundle

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
ASSIGNMENT = "testing__C179819__NRS-484B-633-2__motor_vehicle_driver"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def audit(root, case_id, *, diagnostic_protocol=False):
    root = Path(root).resolve()
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("exact selected bridge case required")
    receipt = load(root / "original-source-receipt.json")
    fixture = root / "fixture-provenance.json"
    diagnostic = fixture.is_file() or receipt.get("diagnostic_fixture") is True
    if diagnostic and not diagnostic_protocol:
        raise ValueError("original Native attempt required; diagnostic fixture rejected")
    if diagnostic_protocol and not diagnostic:
        raise ValueError("diagnostic protocol requires marked synthetic source")
    if receipt.get("case_id") != case_id or receipt.get("world_restored") is not True and not diagnostic:
        raise ValueError("exact original owner closure missing")
    count = 9 if diagnostic_protocol else 900
    if receipt.get("source_frame_count", count) != count:
        raise ValueError("complete original frame count differs")
    for file, key in (("bridge-site.json", "site_sha256"),
                      ("original-motion.jsonl", "trace_sha256"),
                      ("video_frames.jsonl", "frame_map_sha256"),
                      ("camera-source-manifest.json", "camera_manifest_sha256")):
        if receipt.get(key) != sha(root / file):
            raise ValueError("original source hash changed: " + file)
    site = verify_site_bundle(root / "bridge-site.json", receipt["site_sha256"], case_id)
    rows = [json.loads(line) for line in (root / "original-motion.jsonl").read_text().splitlines()]
    mapping = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
    camera_manifest = load(root / "camera-source-manifest.json")
    if len(rows) != count or len(mapping) != count or camera_manifest.get("case_id") != case_id:
        raise ValueError("original motion or four-camera map incomplete")
    if set(camera_manifest.get("cameras", {})) != set(CAMERAS):
        raise ValueError("four original camera sources required")
    from PIL import Image, ImageStat
    pixel_hashes = set()
    for index, (row, frame) in enumerate(zip(rows, mapping)):
        if (row.get("original_frame") != frame.get("native_frame") or
                row.get("time_s") != frame.get("time_s") or frame.get("video_frame") != index):
            raise ValueError("original participant/time join differs")
        for name in CAMERAS:
            item = camera_manifest["cameras"][name][index]
            path = (root / item["path"]).resolve()
            if not path.is_relative_to(root) or path.is_symlink() or sha(path) != item["sha256"]:
                raise ValueError("original camera pixel source changed")
            if item["frame"] != row["original_frame"]:
                raise ValueError("original camera frame identity differs")
            if index in (0, count // 2, count - 1):
                with Image.open(path) as image:
                    rgb = image.convert("RGB")
                    if min(rgb.size) < 180 or max(ImageStat.Stat(rgb).stddev) < 1.0:
                        raise ValueError("original camera pixels blank or too small")
                    pixel_hashes.add(item["sha256"])
    if len(pixel_hashes) < 2:
        raise ValueError("original camera pixels do not change")
    video_sha = {}
    for name in CAMERAS:
        if len(camera_manifest["cameras"][name]) != count:
            raise ValueError("original camera source frame count differs")
        path = root / (name + ".mkv")
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
                                "-show_entries", "stream=nb_read_frames,r_frame_rate,width,height", "-of", "json", str(path)],
                               capture_output=True, text=True, check=True, timeout=120)
        streams = json.loads(probe.stdout).get("streams", [])
        if len(streams) != 1 or streams[0].get("nb_read_frames") != str(count) or streams[0].get("r_frame_rate") != "20/1":
            raise ValueError("original full video frame profile differs")
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-f", "null", "-"],
                       capture_output=True, text=True, check=True, timeout=300)
        video_sha[name] = sha(path)
    measured = measure_crossing(site, rows, case_id, expected_frames=count)
    return {"case_id": case_id, "frames_checked": count, "video_sha256": video_sha,
            "original_source_receipt_sha256": sha(root / "original-source-receipt.json"),
            "measured": measured, "diagnostic_protocol": diagnostic_protocol,
            "original_delivery_claimed": not diagnostic_protocol,
            "checks": ["native_source", "all_participants", "time_join", "full_video_decode",
                       "actual_pixels", "physical_completion"],
            "legal_verdict": "unresolved"}


def diagnostic_fixture(source, case_id, destination):
    """Make visibly changing synthetic camera images in scratch for protocol proof."""
    from PIL import Image
    source, destination = Path(source), Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    for name in ("bridge-site.json", "review-record.txt", "original-motion.jsonl", "video_frames.jsonl"):
        shutil.copy2(source / name, destination / name)
    (destination / "fixture-provenance.json").write_text(json.dumps({"scope": "CPU diagnostic only", "case_id": case_id}) + "\n")
    rows = [json.loads(line) for line in (destination / "original-motion.jsonl").read_text().splitlines()]
    images = {}
    for view_index, name in enumerate(CAMERAS):
        entries = []
        for index, row in enumerate(rows):
            path = destination / f"{name}-{index:06d}.png"
            image = Image.new("RGB", (360, 200))
            pixels = image.load()
            for y in range(200):
                for x in range(360):
                    pixels[x, y] = ((x + 13 * index + 31 * view_index) % 256,
                                    (y + 17 * index) % 256, (x + y + 23 * view_index) % 256)
            image.save(path)
            entries.append({"frame": row["original_frame"], "path": path.name, "sha256": sha(path)})
        images[name] = entries
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-framerate", "20", "-start_number", "0",
                        "-i", f"{name}-%06d.png", "-c:v", "ffv1", f"{name}.mkv"],
                       cwd=destination, check=True, timeout=120)
    manifest = destination / "camera-source-manifest.json"
    manifest.write_text(json.dumps({"case_id": case_id, "cameras": images}, sort_keys=True) + "\n")
    receipt = {"case_id": case_id, "diagnostic_fixture": True, "source_frame_count": len(rows),
               "site_sha256": sha(destination / "bridge-site.json"),
               "trace_sha256": sha(destination / "original-motion.jsonl"),
               "frame_map_sha256": sha(destination / "video_frames.jsonl"),
               "camera_manifest_sha256": sha(manifest)}
    (destination / "original-source-receipt.json").write_text(json.dumps(receipt, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", type=Path)
    parser.add_argument("--diagnostic-source", type=Path)
    parser.add_argument("--mode", choices=("original", "diagnostic-positive", "delivery-negative"), required=True)
    args = parser.parse_args()
    if args.mode == "original":
        if args.attempt is None:
            raise ValueError("original attempt required")
        result = audit(args.attempt, args.case)
    else:
        if args.diagnostic_source is None:
            raise ValueError("marked diagnostic source required")
        scratch = Path(__file__).resolve().parents[2] / ".runtime-work" / "c179819"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="delivery-audit-", dir=scratch) as directory:
            target = Path(directory) / "source"
            diagnostic_fixture(args.diagnostic_source, args.case, target)
            result = audit(target, args.case, diagnostic_protocol=args.mode == "diagnostic-positive")
    print(json.dumps({"case_id": args.case, "diagnostic_protocol_passed": result["diagnostic_protocol"],
                      "frames_checked": result["frames_checked"],
                      "original_delivery_claimed": result["original_delivery_claimed"]}, sort_keys=True))


if __name__ == "__main__":
    main()
