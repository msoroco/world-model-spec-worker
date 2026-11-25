"""Lossless original BGRA source-camera writer; caller joins Native frame IDs."""
import subprocess
from pathlib import Path


class FFV1Writer:
    def __init__(self, path, width, height, fps=20):
        path = Path(path)
        if path.exists() or width <= 0 or height <= 0 or fps <= 0:
            raise ValueError('Fresh path and positive source dimensions/rate required')
        self.path, self.width, self.height, self.fps = path, width, height, fps
        self.frames = 0
        self.exit_code = None
        self.process = subprocess.Popen([
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-n',
            '-f', 'rawvideo', '-pixel_format', 'bgra',
            '-video_size', f'{width}x{height}', '-framerate', str(fps),
            '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-level', '3',
            '-pix_fmt', 'bgr0', str(path)],
            stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    def write(self, bgra):
        if not isinstance(bgra, bytes) or len(bgra) != self.width * self.height * 4:
            raise ValueError('Native BGRA source frame size mismatch')
        if self.process.poll() is not None:
            raise ValueError('Source encoder exited before frame closure')
        self.process.stdin.write(bgra)
        self.frames += 1

    def close(self):
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        code = self.process.wait(timeout=60)
        self.exit_code = code
        error = self.process.stderr.read().decode(errors='replace')
        self.process.stderr.close()
        if code != 0 or self.frames == 0 or not self.path.is_file():
            raise ValueError('FFV1 source encoder failed: ' + error[-1000:])
        return {'path': str(self.path), 'frames': self.frames,
                'width': self.width, 'height': self.height, 'fps': self.fps,
                'encoding': 'ffv1-lossless'}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
