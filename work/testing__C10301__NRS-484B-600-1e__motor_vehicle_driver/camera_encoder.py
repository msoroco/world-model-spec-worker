"""Stream original BGRA source-camera frames to lossless FFV1 Matroska.

One writer per named source camera. Caller joins Native sensor frame IDs before
writing and closes every encoder before marking the capture sealed.
"""

import subprocess
from pathlib import Path


class FFV1Writer:
    def __init__(self, path: Path, width: int, height: int, fps: int = 20):
        path = Path(path)
        if path.exists() or width <= 0 or height <= 0 or fps <= 0:
            raise ValueError("Fresh path and positive video dimensions/rate required")
        self.path, self.width, self.height, self.fps = path, width, height, fps
        self.frames = 0
        self.process = subprocess.Popen([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-n",
            "-f", "rawvideo", "-pixel_format", "bgra",
            "-video_size", f"{width}x{height}", "-framerate", str(fps),
            "-i", "pipe:0", "-an", "-c:v", "ffv1", "-level", "3",
            "-pix_fmt", "bgr0", str(path)],
            stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    def write(self, bgra: bytes):
        if not isinstance(bgra, bytes) or len(bgra) != self.width * self.height * 4:
            raise ValueError("Native BGRA frame size mismatch")
        if self.process.poll() is not None:
            raise ValueError("Video encoder exited before source closure")
        self.process.stdin.write(bgra)
        self.frames += 1

    def close(self):
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        code = self.process.wait(timeout=60)
        error = self.process.stderr.read().decode(errors="replace")
        self.process.stderr.close()
        if code != 0 or self.frames == 0 or not self.path.is_file():
            raise ValueError("FFV1 source encoder failed: " + error[-1000:])
        return {"path": str(self.path), "frames": self.frames,
                "width": self.width, "height": self.height, "fps": self.fps,
                "encoding": "ffv1-lossless"}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
