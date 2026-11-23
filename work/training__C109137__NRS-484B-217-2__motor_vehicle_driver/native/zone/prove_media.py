"""Diagnostic FFV1 frame-count proof for all four required camera sources."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from build import FRAMES, RATE
from saved import CAMERAS, media_hash

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make(path, frames):
    command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
               "-f", "lavfi", "-i", f"color=c=blue:s=32x32:r={RATE}",
               "-frames:v", str(frames), "-c:v", "ffv1", str(path)]
    run = subprocess.run(command, capture_output=True, text=True, timeout=120)
    if run.returncode:
        raise RuntimeError("Diagnostic FFV1 encode failed: " + run.stderr)


def prove():
    if len(CAMERAS) != 4 or FRAMES != 600 or RATE != 20:
        raise ValueError("Four-camera 30-second media contract changed")
    positives = []
    negatives = []
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        for name in CAMERAS:
            path = folder / (name + ".mkv")
            make(path, FRAMES)
            if media_hash(path) != sha(path):
                raise AssertionError("Decoded media hash mismatch")
            positives.append({"camera": name, "frames": FRAMES, "sha256": sha(path)})
            path.unlink()
            try:
                media_hash(path)
            except ValueError as exc:
                negatives.append({"camera": name, "mutation": "missing_video", "error": str(exc)})
            else:
                raise AssertionError("Missing source camera accepted")
            make(path, FRAMES - 1)
            try:
                media_hash(path)
            except ValueError as exc:
                negatives.append({"camera": name, "mutation": "short_video", "error": str(exc)})
            else:
                raise AssertionError("Short source camera accepted")
    receipt = {"format": "c109137-four-camera-diagnostic-media-proof-v1",
               "frames": FRAMES, "rate_hz": RATE, "camera_names": list(CAMERAS),
               "positives": positives, "negatives": negatives,
               "passed": len(positives) == 4 and len(negatives) == 8,
               "scope": "Generated diagnostic FFV1 only; no original Native pixels or physical claim."}
    path = HERE / "four-camera-media-proof.json"
    path.write_text(json.dumps(receipt, indent=2) + "\n")
    return {"positive_count": len(positives), "negative_count": len(negatives)}


if __name__ == "__main__":
    print(json.dumps(prove()))
