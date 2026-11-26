"""Render verified original PNG camera sources as lossless saved-only videos."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from capture_seal import CAMERAS, seal


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(args: list[str]) -> str:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        raise ValueError("saved video processing failed: " + result.stderr[-1000:])
    return result.stdout


def _encode(stage: Path, frames: list[dict], output: Path) -> None:
    process = subprocess.Popen(
        ["ffmpeg", "-nostdin", "-v", "error", "-f", "image2pipe", "-framerate", "20",
         "-vcodec", "png", "-i", "pipe:0", "-c:v", "ffv1", "-level", "3",
         "-pix_fmt", "yuv420p", str(output)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for frame in frames:
            process.stdin.write((stage / frame["path"]).read_bytes())
        process.stdin.close()
        process.stdin = None
        _, error = process.communicate()
    except Exception:
        process.kill()
        process.wait()
        raise
    if process.returncode:
        raise ValueError("saved video encoder failed: " + error.decode(errors="replace")[-1000:])


def process_saved(stage: Path, output: Path, *, diagnostic_fixture: bool = False) -> dict:
    stage, output = Path(stage), Path(output)
    if output.exists():
        raise ValueError("saved output already exists")
    capture = seal(stage, diagnostic_fixture=diagnostic_fixture)
    manifest = json.loads((stage / "camera-source-manifest.json").read_text())
    retained = {name: sha(stage / name) for name in
                ("source-packet.json", "original-ticks.jsonl",
                 "camera-source-manifest.json", "native-owner-release.json")}
    for frames in manifest["cameras"].values():
        for frame in frames:
            retained[frame["path"]] = sha(stage / frame["path"])
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="saved-stage-", dir=output.parent) as temp:
        derived = Path(temp)
        videos = {}
        for name in CAMERAS:
            video = derived / (name + ".mkv")
            _encode(stage, manifest["cameras"][name], video)
            probe = json.loads(_run(["ffprobe", "-v", "error", "-count_frames",
                                     "-select_streams", "v:0", "-show_entries",
                                     "stream=width,height,nb_read_frames,r_frame_rate",
                                     "-of", "json", str(video)]))["streams"][0]
            expected_size = capture["camera_sources"][name]["dimensions"]
            if ([probe["width"], probe["height"]] != expected_size or
                    probe["r_frame_rate"] != "20/1" or
                    int(probe["nb_read_frames"]) != capture["source_frame_count"]):
                raise ValueError("saved video metadata differs: " + name)
            _run(["ffmpeg", "-v", "error", "-i", str(video), "-f", "null", "-"])
            videos[name] = {"path": video.name, "sha256": sha(video),
                            "decoded_frames": int(probe["nb_read_frames"])}
        for name, digest in retained.items():
            if sha(stage / name) != digest:
                raise ValueError("original source changed during saved processing: " + name)
        report = {"format": "c230235-saved-only-v1", "case_id": capture["case_id"],
                  "source_kind": capture["source_kind"],
                  "capture_seal": capture,
                  "retained_source_sha256": retained,
                  "videos": videos,
                  "physical_acceptance_claimed": False,
                  "legal_acceptance_claimed": False}
        (derived / "saved-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        derived.rename(output)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    args = parser.parse_args()
    print(json.dumps(process_saved(args.stage, args.output,
                                   diagnostic_fixture=args.diagnostic_fixture),
                     sort_keys=True))
