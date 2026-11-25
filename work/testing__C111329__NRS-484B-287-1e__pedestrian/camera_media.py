"""Stream and independently decode four original Native camera sources.

The small profile override is only for CPU tests. Production uses the pinned
worker capture dimensions; a decoded pixel stream never proves walker visibility.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
PROFILE = {"overview": (1920, 1080), "approach": (1280, 720),
           "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def _sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _probe(path):
    output = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,codec_name",
        "-of", "json", str(path)], text=True)
    streams = json.loads(output).get("streams", [])
    if len(streams) != 1:
        raise ValueError("one original video stream required")
    return streams[0]


class FourCameraRecorder:
    """Encode one synchronized BGRA image per original world tick."""

    def __init__(self, attempt, profile=None, *, diagnostic=False, factory=subprocess.Popen):
        self.attempt = Path(attempt).resolve()
        if not self.attempt.is_dir():
            raise ValueError("existing attempt directory required")
        self.profile = dict(PROFILE if profile is None else profile)
        if set(self.profile) != set(CAMERAS) or (not diagnostic and self.profile != PROFILE):
            raise ValueError("four pinned camera dimensions required")
        self.processes = {}
        self.paths = {}
        self.count = 0
        self.previous_frame = None
        self.closed = False
        try:
            for name in CAMERAS:
                width, height = self.profile[name]
                if not isinstance(width, int) or not isinstance(height, int) or width < 1 or height < 1:
                    raise ValueError("camera dimensions invalid")
                path = self.attempt / (name + ".mkv")
                if path.exists():
                    raise ValueError("original camera output already exists")
                command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                           "-f", "rawvideo", "-pixel_format", "bgra", "-video_size",
                           f"{width}x{height}", "-framerate", "20", "-i", "pipe:0", "-an",
                           "-c:v", "ffv1", "-pix_fmt", "bgra", str(path)]
                self.paths[name] = path
                self.processes[name] = factory(command, stdin=subprocess.PIPE,
                                               stderr=subprocess.PIPE)
        except BaseException:
            self.close(require_success=False)
            raise

    def append(self, frame, images):
        if self.closed:
            raise ValueError("camera recorder closed")
        if type(frame) is not int or (self.previous_frame is not None and frame != self.previous_frame + 1):
            raise ValueError("camera original frame discontinuity")
        if not isinstance(images, dict) or set(images) != set(CAMERAS):
            raise ValueError("four original camera images required")
        # Validate all views before writing any one view for this tick.
        for name in CAMERAS:
            image = images[name]
            width, height = self.profile[name]
            if (getattr(image, "frame", None) != frame or
                    getattr(image, "width", None) != width or
                    getattr(image, "height", None) != height or
                    not isinstance(getattr(image, "raw_data", None), bytes) or
                    len(image.raw_data) != width * height * 4):
                raise ValueError(name + " original BGRA frame or dimensions differ")
        for name in CAMERAS:
            data = images[name].raw_data
            written = self.processes[name].stdin.write(data)
            if written != len(data):
                raise ValueError(name + " original camera frame incomplete")
        self.previous_frame = frame
        self.count += 1

    def close(self, *, require_success=True):
        if self.closed:
            return
        self.closed = True
        errors = []
        for name, process in self.processes.items():
            try:
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
                code = process.wait(timeout=180)
                if code and require_success:
                    errors.append(name + " FFV1 encoder failed")
            except BaseException as exc:
                process.kill()
                process.wait()
                errors.append(name + " encoder failed: " + str(exc))
            finally:
                if process.stderr:
                    process.stderr.close()
        if errors and require_success:
            raise ValueError("; ".join(errors))

    def source_receipt(self):
        if not self.closed or self.count <= 0:
            raise ValueError("closed nonempty original camera recorder required")
        return {name: {"path": path.name,
                       "sha256": _sha_file(path),
                       "frames": self.count}
                for name, path in self.paths.items()}


def audit_original_media(attempt, sources, expected_frames, *, profile=None,
                         diagnostic=False):
    """Decode every pixel of every frame and reject short/stale source videos."""
    attempt = Path(attempt).resolve()
    dimensions = dict(PROFILE if profile is None else profile)
    if set(sources) != set(CAMERAS) or set(dimensions) != set(CAMERAS):
        raise ValueError("four original camera sources required")
    if not diagnostic and dimensions != PROFILE:
        raise ValueError("production camera profile differs")
    if type(expected_frames) is not int or expected_frames < 1:
        raise ValueError("expected original frame count required")
    result = {}
    for name in CAMERAS:
        ref = sources[name]
        if not isinstance(ref, dict) or not isinstance(ref.get("path"), str):
            raise ValueError(name + " camera source reference missing")
        original = attempt / ref["path"]
        path = original.resolve()
        if not path.is_relative_to(attempt) or original.is_symlink() or not path.is_file():
            raise ValueError(name + " camera source missing or escapes attempt")
        before = _sha_file(path)
        if before != ref.get("sha256") or ref.get("frames") != expected_frames:
            raise ValueError(name + " original camera source hash/count mismatch")
        metadata = _probe(path)
        width, height = dimensions[name]
        if ([metadata.get("width"), metadata.get("height")] != [width, height] or
                metadata.get("r_frame_rate") != "20/1" or
                metadata.get("codec_name") != "ffv1"):
            raise ValueError(name + " original camera codec, dimensions or rate differ")
        command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                   "-i", str(path), "-vsync", "0", "-f", "rawvideo", "-pix_fmt",
                   "rgb24", "pipe:1"]
        process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        digest = hashlib.sha256()
        count = 0
        frame_bytes = width * height * 3
        try:
            while True:
                block = process.stdout.read(frame_bytes)
                if not block:
                    break
                if len(block) != frame_bytes or count >= expected_frames:
                    raise ValueError(name + " truncated or extra decoded frame")
                digest.update(block)
                count += 1
            code = process.wait(timeout=180)
            if code:
                raise ValueError(name + " full decode failed")
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stderr.close()
        if count != expected_frames or _sha_file(path) != before:
            raise ValueError(name + " incomplete or changed full decode")
        result[name] = {"video_sha256": before, "frames": count,
                        "rgb_sequence_sha256": digest.hexdigest(),
                        "dimensions": [width, height]}
    return {"format": "c111329-original-four-view-decode", "diagnostic": diagnostic,
            "expected_frames": expected_frames, "cameras": result,
            "auditor_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "physical_visibility": "unverified", "legal_conclusion": "not_assessed"}


def verify_media_receipt(attempt, sources, receipt_ref, expected_frames, *, diagnostic=False):
    """Check the sealed full-decode receipt against current auditor and video bytes."""
    attempt = Path(attempt).resolve()
    if not isinstance(receipt_ref, dict) or not isinstance(receipt_ref.get("path"), str):
        raise ValueError("original full-decode receipt missing")
    original = attempt / receipt_ref["path"]
    path = original.resolve()
    if not path.is_relative_to(attempt) or original.is_symlink() or not path.is_file():
        raise ValueError("original full-decode receipt escapes attempt")
    if _sha_file(path) != receipt_ref.get("sha256"):
        raise ValueError("original full-decode receipt hash mismatch")
    receipt = json.loads(path.read_text())
    if (receipt.get("format") != "c111329-original-four-view-decode" or
            receipt.get("diagnostic") != diagnostic or
            receipt.get("expected_frames") != expected_frames or
            receipt.get("auditor_sha256") != hashlib.sha256(Path(__file__).read_bytes()).hexdigest() or
            set(receipt.get("cameras", {})) != set(CAMERAS)):
        raise ValueError("original full-decode receipt stale or incomplete")
    for name in CAMERAS:
        ref = sources.get(name)
        if not isinstance(ref, dict) or not isinstance(ref.get("path"), str):
            raise ValueError(name + " original camera source missing")
        original = attempt / ref["path"]
        video = original.resolve()
        if not video.is_relative_to(attempt) or original.is_symlink() or not video.is_file():
            raise ValueError(name + " original camera source escapes attempt")
        digest = _sha_file(video)
        if (digest != ref.get("sha256") or
                receipt["cameras"][name].get("video_sha256") != digest or
                receipt["cameras"][name].get("frames") != expected_frames):
            raise ValueError(name + " original full-decode source changed")
    return receipt
