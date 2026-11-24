"""Stream original synchronized CARLA BGRA images into four lossless videos.

The caller owns the camera actors and a synchronizer that returns their original
image objects. This adapter checks identity, dimensions and world-frame joins.
It never creates or substitutes an image for a missing sensor observation.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from native_readback import CAMERAS

PROFILE = {"overview": (1920, 1080), "approach": (1280, 720),
           "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class NativeCameraRecorder:
    """Encode four original camera images, one synchronized world tick at a time."""

    def __init__(self, output: Path, sensors: dict, *, dimensions=None,
                 expected_frames: int = 900):
        self.output = Path(output)
        if self.output.exists() and any(self.output.iterdir()):
            raise ValueError("original camera output must be empty")
        self.output.mkdir(parents=True, exist_ok=True)
        self.dimensions = dict(PROFILE if dimensions is None else dimensions)
        if set(sensors) != set(CAMERAS) or set(self.dimensions) != set(CAMERAS):
            raise ValueError("four exact original camera actors and dimensions required")
        ids = [getattr(sensors[name], "id", None) for name in CAMERAS]
        if any(type(value) is not int or value < 0 for value in ids) or len(set(ids)) != 4:
            raise ValueError("four distinct original camera sensor IDs required")
        if type(expected_frames) is not int or expected_frames < 1:
            raise ValueError("positive original frame count required")
        self.sensor_ids = dict(zip(CAMERAS, ids))
        self.expected_frames = expected_frames
        self.processes = {}
        self.count = 0
        self.first_frame = None
        self.closed = False

    def _start(self, name: str):
        width, height = self.dimensions[name]
        if type(width) is not int or type(height) is not int or width < 1 or height < 1:
            raise ValueError("invalid original camera dimensions")
        path = self.output / f"{name}.mkv"
        process = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-xerror", "-y", "-f", "rawvideo",
             "-pixel_format", "bgra", "-video_size", f"{width}x{height}",
             "-framerate", "20", "-i", "pipe:0", "-an", "-c:v", "ffv1",
             "-level", "3", "-pix_fmt", "bgr0", str(path)],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        self.processes[name] = process

    def __call__(self, frame: int, images: dict) -> dict:
        """Consume original sensor images and return camera IDs for actor readback."""
        if self.closed or self.count >= self.expected_frames:
            raise ValueError("original camera capture is closed or complete")
        if type(frame) is not int or set(images) != set(CAMERAS):
            raise ValueError("four synchronized original camera images required")
        if self.first_frame is None:
            self.first_frame = frame
        if frame != self.first_frame + self.count:
            raise ValueError("original camera world frames are not contiguous")
        payloads = {}
        for name in CAMERAS:
            image = images[name]
            width, height = self.dimensions[name]
            if (type(getattr(image, "frame", None)) is not int or image.frame != frame or
                    getattr(image, "sensor_id", None) != self.sensor_ids[name] or
                    getattr(image, "width", None) != width or
                    getattr(image, "height", None) != height):
                raise ValueError(f"original camera identity, frame or dimensions mismatch: {name}")
            raw = getattr(image, "raw_data", None)
            if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != width * height * 4:
                raise ValueError(f"original BGRA pixel payload missing or incomplete: {name}")
            payloads[name] = raw
        for name in CAMERAS:
            if name not in self.processes:
                self._start(name)
            process = self.processes[name]
            if process.poll() is not None:
                raise ValueError(f"original camera encoder exited early: {name}")
            try:
                process.stdin.write(payloads[name])
            except (BrokenPipeError, OSError) as exc:
                raise ValueError(f"original camera encoder write failed: {name}") from exc
        self.count += 1
        return {name: frame for name in CAMERAS}

    def seal(self, packet_dir: Path) -> dict:
        """Close encoders and bind their hashes to the saved source packet."""
        if self.closed or self.count != self.expected_frames or set(self.processes) != set(CAMERAS):
            raise ValueError("complete original four-camera capture required")
        self.closed = True
        for name in CAMERAS:
            process = self.processes[name]
            process.stdin.close()
            error = process.stderr.read().decode("utf-8", "replace")
            process.stderr.close()
            if process.wait() != 0:
                raise ValueError(f"original camera encode failed: {name}: {error[:200]}")
        packet_dir = Path(packet_dir)
        packet_path = packet_dir / "source-packet.json"
        packet = json.loads(packet_path.read_text())
        if packet.get("source_kind") != "original_saved_acquisition" or "camera_media" in packet:
            raise ValueError("unbound original source packet required")
        media = {}
        for name in CAMERAS:
            source = self.output / f"{name}.mkv"
            target = packet_dir / source.name
            if target.exists() or not source.is_file() or source.stat().st_size == 0:
                raise ValueError("camera media target collision or empty encode")
            source.replace(target)
            media[name] = {"path": target.name, "sha256": _sha(target),
                           "frame_count": self.count, "fps": 20,
                           "sensor_id": self.sensor_ids[name]}
        packet["camera_media"] = media
        packet_path.write_text(json.dumps(packet, indent=2) + "\n")
        return media

    def abort(self) -> None:
        """Release encoders after an incomplete or rejected capture."""
        if self.closed:
            return
        self.closed = True
        for process in self.processes.values():
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
            if process.poll() is None:
                process.terminate()
            process.wait()
            if process.stderr and not process.stderr.closed:
                process.stderr.close()
