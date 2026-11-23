"""Short synthetic decode check of the four-camera composition profile."""
import hashlib
import json
from pathlib import Path
import subprocess

from capture import COMPOSE_LAYOUT

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = ROOT / ".runtime-work" / "c10365-media-profile"
CAMERAS = (("overview", 1920, 1080, "red"),
           ("rider_forward", 1280, 720, "green"),
           ("officer_side", 1280, 720, "blue"),
           ("device_side", 1280, 720, "yellow"))


def command(args):
    run = subprocess.run(args, capture_output=True, text=True, timeout=300)
    if run.returncode:
        raise RuntimeError(run.stderr[-2000:])
    return run


def inspect(path):
    run = command(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                   "-show_entries", "stream=codec_name,width,height,nb_read_frames",
                   "-of", "json", str(path)])
    return json.loads(run.stdout)["streams"][0]


def prove():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, width, height, color in CAMERAS:
        path = OUT / (name + ".mkv")
        command(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                 "-f", "lavfi", "-i", f"color=c={color}:s={width}x{height}:r=20:d=0.4",
                 "-frames:v", "8", "-c:v", "ffv1", str(path)])
        row = inspect(path)
        if (row.get("codec_name") != "ffv1" or row.get("width") != width or
                row.get("height") != height or row.get("nb_read_frames") != "8"):
            raise ValueError("Synthetic source camera profile failed: " + name)
    composed = OUT / "raw.mkv"
    command(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
             *sum((["-i", str(OUT / (name + ".mkv"))] for name, *_ in CAMERAS), []),
             "-filter_complex", COMPOSE_LAYOUT, "-an", "-c:v", "ffv1", str(composed)])
    row = inspect(composed)
    if (row.get("codec_name") != "ffv1" or row.get("width") != 3840 or
            row.get("height") != 1800 or row.get("nb_read_frames") != "8"):
        raise ValueError("Synthetic composed video profile failed")
    digest = hashlib.sha256(composed.read_bytes()).hexdigest()
    receipt = {"format": "c10365-synthetic-media-profile-v1", "passed": True,
               "source_count": 4, "source_frames": 8, "composed_frames": 8,
               "composed_dimensions": [3840, 1800], "composed_sha256": digest,
               "physical_original_observed": False, "delivery_ready": False}
    (HERE / "media-profile-proof.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    print(json.dumps(prove()))
