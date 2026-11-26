"""Independent source and pixel audit for the two selected left-turn cases.

The selftests use synthetic images. A delivery audit requires a separate original
Native attempt and reviewer pixel boxes for all three road users.
"""
import argparse
import io
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageStat


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
ROOT = Path(__file__).resolve().parent
PREFIX = "training__C329654__NRS-484B-253__motor_vehicle_driver__selected_d457f261__condition_"


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def check_sources(files, case, count=600):
    actor = rows(files["left-turn-actors.jsonl"])
    mapping = rows(files["video_frames.jsonl"])
    cameras = rows(files["camera-frames.jsonl"])
    evidence = rows(files["capture/evidence.jsonl"])
    trace = rows(files["trace.jsonl"])
    if any(len(part) != count for part in (actor, mapping, cameras, evidence, trace)):
        raise ValueError("Full original source frame coverage missing")
    opponent_ids = None
    for index, (a, m, c, e, t) in enumerate(zip(actor, mapping, cameras, evidence, trace)):
        frame = a["native_frame"]
        if (a["case_id"] != case or a["frame"] != index or m["video_frame"] != index
                or c["frame"] != index or m["native_frame"] != frame
                or c["native_frame"] != frame or e["original_frame"] != frame
                or t["frame"] != frame or abs(a["time_s"] - m["time_s"]) > 1e-6
                or abs(a["time_s"] - e["recording_time_s"]) > 1e-6):
            raise ValueError("Original actor/camera/evidence time join differs")
        if set(m["camera_native_frames"]) != set(CAMERAS) or any(
                m["camera_native_frames"][view] != frame for view in CAMERAS):
            raise ValueError("Four-camera original frame join differs")
        ids = {item["actor_id"] for item in a["oncoming"]}
        if len(a["oncoming"]) != 2 or len(ids) != 2 or (opponent_ids is not None and ids != opponent_ids):
            raise ValueError("Both stable opposing road users required")
        opponent_ids = ids
        if a["ego"].get("left_indicator_on") is None:
            raise ValueError("Original ego left signal readback missing")
    return {"frames": count, "opposing_ids": sorted(opponent_ids),
            "cameras": list(CAMERAS)}


def check_pixel_box(image, box):
    if not isinstance(box, list) or len(box) != 4 or any(type(x) is not int for x in box):
        raise ValueError("Reviewed pixel box has invalid coordinates")
    x0, y0, x1, y1 = box
    if not (0 <= x0 < x1 <= image.width and 0 <= y0 < y1 <= image.height):
        raise ValueError("Reviewed pixel box exceeds source video")
    crop = image.convert("RGB").crop(tuple(box))
    extrema = ImageStat.Stat(crop).extrema
    if max(hi - lo for lo, hi in extrema) < 8:
        raise ValueError("Reviewed pixel box has no visible image variation")
    return {"bounds": box, "image_size": [image.width, image.height],
            "pixel_variation": max(hi - lo for lo, hi in extrema)}


def decoded_frame(path, frame):
    command = ["ffmpeg", "-v", "error", "-i", str(path), "-vf",
               f"select=eq(n\\,{frame})", "-frames:v", "1", "-f", "image2pipe",
               "-vcodec", "png", "-"]
    done = subprocess.run(command, capture_output=True, check=True)
    if not done.stdout:
        raise ValueError("Reviewed source frame failed to decode")
    return Image.open(io.BytesIO(done.stdout)).convert("RGB")


def audit_original(attempt, case, review):
    attempt = Path(attempt)
    provenance = json.loads((attempt / "acquisition-provenance.json").read_text())
    if provenance.get("provenance_kind") != "native" or provenance.get("diagnostic_fixture"):
        raise ValueError("Delivery audit requires original Native acquisition")
    names = ("left-turn-actors.jsonl", "video_frames.jsonl", "camera-frames.jsonl",
             "capture/evidence.jsonl", "trace.jsonl")
    sources = check_sources({name: attempt / name for name in names}, case)
    reviewed = json.loads(Path(review).read_text())
    observations = reviewed.get("observations", [])
    if {item.get("role") for item in observations} != {"ego", "initial", "subsequent"}:
        raise ValueError("Pixel review must cover all three road users")
    pixels = []
    for item in observations:
        view = item["camera"]
        frame = item["video_frame"]
        if view not in CAMERAS or type(frame) is not int or not 0 <= frame < 600:
            raise ValueError("Pixel review references another camera or frame")
        image = decoded_frame(attempt / (view + ".mkv"), frame)
        pixels.append({"role": item["role"], "view": view, "frame": frame,
                       **check_pixel_box(image, item["bbox_xyxy"])})
    for view in CAMERAS:
        path = attempt / (view + ".mkv")
        done = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path),
                               "-f", "null", "-"], capture_output=True)
        if done.returncode:
            raise ValueError("Full source video decode failed: " + view)
    return {"format": "c329654-original-delivery-audit-v1", "case_id": case,
            "source_join": sources, "reviewed_pixels": pixels,
            "four_source_videos_fully_decoded": True,
            "legal_priority_verdict": None}


def selftest(case, negative):
    suffix = case.removeprefix(PREFIX)[-1]
    if case != PREFIX + suffix or suffix not in "ab":
        raise ValueError("Select one exact case")
    spec = json.loads((ROOT / f"selected-{suffix}-fixture.json").read_text())
    required = ("left-turn-actors.jsonl", "video_frames.jsonl", "camera-frames.jsonl",
                "capture/evidence.jsonl", "trace.jsonl")
    import tempfile
    with tempfile.TemporaryDirectory(dir=ROOT.parents[2] / ".runtime-work",
                                         prefix="c329654-audit-") as temp:
        base = Path(temp)
        paths = {}
        for name in required:
            path = base / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(spec["files"][name])
            paths[name] = path
        source = check_sources(paths, case)
    image = Image.new("RGB", (128, 72), (10, 15, 20))
    ImageDraw.Draw(image).rectangle((20, 15, 65, 55), fill=(220, 170, 30))
    if negative:
        check_pixel_box(image, [20, 15, 129, 55])
        raise AssertionError("Out-of-bounds pixel box was accepted")
    pixel = check_pixel_box(image, [15, 10, 70, 60])
    return {"case_id": case, "source_join": source, "pixel_mechanics": pixel,
            "scope": "synthetic CPU audit mechanics, not original pixel review"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt")
    parser.add_argument("--review")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--negative-selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest or args.negative_selftest:
        print(json.dumps(selftest(args.case, args.negative_selftest), sort_keys=True))
    elif args.attempt and args.review:
        print(json.dumps(audit_original(args.attempt, args.case, args.review), sort_keys=True))
    else:
        parser.error("Supply --attempt and --review for original delivery audit")
