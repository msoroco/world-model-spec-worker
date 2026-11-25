"""Verify an independent review against original and encoded camera pixels.

The review is an external observation. This module never creates one or infers
visibility from a case label. Each cited frame must still match both original
PNG bytes and the corresponding saved lossless video frame.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from io import BytesIO
from pathlib import Path

from PIL import Image

from freight_contract import SourceError
from saved_delivery import CAMERAS


PHASES = {"approach": range(0, 300), "halt": range(300, 700),
          "freight": range(700, 900)}
ROLES = {
    "overview": ("yellow_curb_visible", "ego_visible", "sign_visible"),
    "approach": ("yellow_curb_visible", "ego_visible"),
    "reference_corner": ("yellow_curb_visible", "ego_visible", "cargo_visible"),
    "driver_reference": ("ego_visible", "sign_visible"),
}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise SourceError(reason)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode_frame(video: Path, index: int) -> bytes:
    command = ["ffmpeg", "-nostdin", "-v", "error", "-i", str(video),
               "-vf", f"select=eq(n\\,{index})", "-frames:v", "1",
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    result = subprocess.run(command, capture_output=True)
    require(result.returncode == 0, "reviewed video frame failed to decode")
    return result.stdout


def audit_pixels(manifest: dict, *, attempt: Path, review: dict,
                 decode=decode_frame) -> dict:
    attempt = Path(attempt).resolve(strict=True)
    require(review.get("format") == "worker-freight-pixel-review-v1",
            "independent pixel review format missing")
    require(review.get("case_id") == manifest.get("case_id") and
            review.get("native_result_sha256") == manifest.get("native_result_sha256"),
            "independent pixel review source identity differs")
    require(isinstance(review.get("reviewer"), str) and review["reviewer"].strip() and
            isinstance(review.get("method"), str) and review["method"].strip(),
            "independent pixel review attribution missing")
    views = review.get("views")
    require(isinstance(views, dict) and set(views) == set(CAMERAS),
            "independent pixel review omits a camera")
    receipt = {}
    for name, size in CAMERAS.items():
        video_ref = manifest["media"][name]
        video = (attempt / video_ref["path"]).resolve(strict=True)
        require(video.is_relative_to(attempt) and sha(video) == video_ref["sha256"],
                "reviewed video changed: " + name)
        entries = views[name]
        require(isinstance(entries, list) and len(entries) >= 3,
                "review needs approach, halt and freight frames: " + name)
        seen = set()
        phase_seen = set()
        for entry in entries:
            frame = entry.get("frame")
            require(type(frame) is int and 0 <= frame < 900 and frame not in seen,
                    "invalid reviewed frame: " + name)
            seen.add(frame)
            phase_seen.update(phase for phase, span in PHASES.items() if frame in span)
            require(all(entry.get(role) is True for role in ROLES[name]),
                    "required physical feature not visible: " + name)
            source = (attempt / "cameras" / name / f"{frame:06d}.png").resolve(strict=True)
            require(source.is_relative_to(attempt) and source.is_file() and
                    sha(source) == entry.get("original_png_sha256"),
                    "reviewed original pixel source differs: " + name)
            with Image.open(BytesIO(source.read_bytes())) as image:
                require(image.size == size, "reviewed original pixel size differs: " + name)
                original_rgb = image.convert("RGB").tobytes()
            require(decode(video, frame) == original_rgb,
                    "encoded video pixels differ from reviewed original: " + name)
        require(phase_seen == set(PHASES), "review does not span physical phases: " + name)
        receipt[name] = sorted(seen)
    return {"format": "worker-freight-pixel-audit-v1",
            "case_id": manifest["case_id"], "actual_pixels_reviewed": True,
            "reviewed_frames": receipt, "legal_conclusion": "unresolved"}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--review", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    review = json.loads(args.review.read_text(encoding="utf-8"))
    print(json.dumps(audit_pixels(manifest, attempt=args.attempt, review=review),
                     sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
