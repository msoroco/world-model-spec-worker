"""Independent audit of sealed Native motion, original pixels and review."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from PIL import Image

from original_camera_recorder import PRODUCTION_PROFILE, VIEWS


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(attempt, name, seal):
    require(isinstance(name, str) and Path(name).name == name and
            name in seal["sources"], "sealed original source absent: " + str(name))
    path = attempt / name
    require(path.is_file() and sha(path) == seal["sources"][name],
            "original source changed: " + name)
    return path


def media_audit(path, frames, dimensions):
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-count_frames", "-show_entries",
                            "stream=codec_name,width,height,r_frame_rate,nb_read_frames",
                            "-of", "json", str(path)], capture_output=True, text=True,
                           check=True)
    streams = json.loads(probe.stdout).get("streams", [])
    require(len(streams) == 1, "one original video stream required")
    stream = streams[0]
    require(stream.get("codec_name") == "ffv1" and
            (stream.get("width"), stream.get("height")) == dimensions and
            stream.get("r_frame_rate") == "20/1" and
            int(stream.get("nb_read_frames", -1)) == frames,
            "full original video profile differs")
    subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path),
                    "-f", "null", "-"], capture_output=True, check=True)


def pixel_join(video, png, index, dimensions):
    with Image.open(png) as image:
        require(image.size == dimensions, "original PNG dimensions differ")
        pixels = image.convert("RGB").tobytes()
    decoded = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i",
                              str(video), "-vf", f"select=eq(n\\,{index})",
                              "-vsync", "0", "-frames:v", "1", "-f", "rawvideo",
                              "-pix_fmt", "rgb24", "-"], capture_output=True,
                             check=True)
    require(decoded.stdout == pixels and len(pixels) == dimensions[0] * dimensions[1] * 3,
            "original PNG/video pixel join differs")
    return hashlib.sha256(pixels).hexdigest()


def run(case, attempt, processed):
    attempt = attempt.resolve()
    seal_path = attempt / "capture-seal.json"
    seal = read(seal_path)
    require(seal.get("format") == "worker-sealed-capture" and
            seal.get("provenance_kind") == "native" and
            seal.get("diagnostic_fixture") is False and seal.get("frames") == 900 and
            seal.get("events") == ["capture_finished", "encoders_closed",
                                   "restoration_verified"] and
            seal.get("restoration", {}).get("restored") is True and
            seal.get("encoder_exit_codes") == {view: 0 for view in VIEWS},
            "original Native capture and closure unverified")
    sources = seal.get("sources")
    require(isinstance(sources, dict), "original source inventory absent")
    canonical = json.dumps(sources, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False).encode()
    require(hashlib.sha256(canonical).hexdigest() == seal.get("source_digest"),
            "original capture digest differs")
    mandatory = {"construction.json", "runner.py", "config.json", "site.json",
                 "devices.json", "routes.json", "original-history.json",
                 "video_frames.jsonl", "trace.jsonl", "acquisition.json",
                 "source-frame-samples.json", "camera-media-refs.json"}
    mandatory.update(view + ".mkv" for view in VIEWS)
    require(mandatory <= set(sources), "original source inventory incomplete")
    for name in mandatory:
        source(attempt, name, seal)
    revision = seal.get("native_revision", {})
    require(revision.get("construction_sha256") == sources["construction.json"] and
            revision.get("runner_sha256") == sources["runner.py"],
            "Native implementation revision differs")
    packet = read(attempt / "original-history.json")
    require(packet.get("case_id") == case and len(packet.get("frames", [])) == 900,
            "wrong exact original motion history")
    mapping = [json.loads(line) for line in
               (attempt / "video_frames.jsonl").read_text().splitlines()]
    require(len(mapping) == 900 and all(row["video_frame"] == i and
            row["carla_frame"] == packet["frames"][i]["native_frame"] and
            abs(row["time_s"] - packet["frames"][i]["time_s"]) < .001
            for i, row in enumerate(mapping)), "Native/video identity join differs")
    media = read(attempt / "camera-media-refs.json")
    samples = read(attempt / "source-frame-samples.json")
    require(samples.get("case_id") == case and set(media) == set(VIEWS) and
            set(samples.get("samples", {})) == set(VIEWS),
            "four original camera sources absent")
    joined = {}
    for view in VIEWS:
        ref = media[view]
        require(ref == {"path": view + ".mkv", "sha256": sources[view + ".mkv"]},
                "original camera reference differs")
        video = source(attempt, ref["path"], seal)
        media_audit(video, 900, PRODUCTION_PROFILE[view])
        refs = samples["samples"][view]
        require(set(refs) == {"0", "450", "899"},
                "original beginning, middle, end pixel samples absent")
        joined[view] = {}
        for index, sample in refs.items():
            relative = sample.get("path")
            require(isinstance(relative, str) and
                    relative == f"source-frame-samples/{view}-{int(index):06d}.png",
                    "original sample path differs")
            png = attempt / relative
            require(png.is_file() and sha(png) == sample.get("sha256") and
                    sources.get(relative) == sample["sha256"],
                    "original PNG source changed")
            joined[view][index] = pixel_join(video, png, int(index),
                                              PRODUCTION_PROFILE[view])
    versions = sorted(processed.resolve().glob("v[0-9][0-9][0-9][0-9]"))
    require(len(versions) == 1, "one reviewed saved processing revision required")
    result_path = versions[0] / "analysis/result.json"
    result = read(result_path)
    check = result.get("physical_checks", {}).get("maneuver", {})
    require(result.get("case_id") == case and
            result.get("provenance_kind") == "native" and
            result.get("maneuver_completed") is True and
            check.get("status") == "met" and
            all(check.get("sources", {}).get(name) == sources[name]
                for name in ("config.json", "trace.jsonl", "video_frames.jsonl")),
            "saved physical crossing lacks source-bound completion")
    review = read(attempt / "independent-source-review.json")
    require(review.get("case_id") == case and review.get("reviewer_id") and
            review.get("reviewer_role") == "independent_source_reviewer" and
            review.get("method") == "manual_original_frame_and_event_review" and
            review.get("legal_verdict_claimed") is False,
            "independent original source review absent")
    require(review.get("source_bindings") == {
        "capture_seal_sha256": sha(seal_path),
        "saved_result_sha256": sha(result_path),
        "original_history_sha256": sources["original-history.json"],
        "video_frame_map_sha256": sources["video_frames.jsonl"],
        "camera_media_sha256": {v: sources[v + ".mkv"] for v in VIEWS},
        "source_frame_samples_sha256": sources["source-frame-samples.json"]},
        "independent review source binding differs")
    require(review.get("sample_rgb_sha256") == joined,
            "independent review did not inspect joined original pixels")
    frame_ids = {frame["native_frame"] for frame in packet["frames"]}
    for name in ("non_through_intersection", "controlling_authority",
                 "counterpart_priority", "yield_timing", "cautious_crossing",
                 "physical_completion", "all_four_views"):
        item = review.get("observations", {}).get(name)
        require(isinstance(item, dict) and item.get("status") == "met" and
                isinstance(item.get("explanation"), str) and
                len(item["explanation"].strip()) >= 20 and
                isinstance(item.get("original_frame_ids"), list) and
                item["original_frame_ids"] and
                all(frame in frame_ids for frame in item["original_frame_ids"]),
                "independent original observation absent: " + name)
    return {"case_id": case, "capture_seal_sha256": sha(seal_path),
            "saved_result_sha256": sha(result_path), "sample_rgb_sha256": joined,
            "independent_review_sha256": sha(attempt / "independent-source-review.json"),
            "checks": ["sealed_native_source", "full_four_video_decode",
                       "sampled_original_pixel_join", "physical_completion",
                       "independent_original_review"],
            "legal_verdict_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--processed", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.attempt, args.processed), sort_keys=True))
