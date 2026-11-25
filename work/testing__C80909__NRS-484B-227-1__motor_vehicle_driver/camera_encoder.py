"""Lossless original Native RGB camera source writer for a fresh capture attempt."""

from pathlib import Path
import subprocess


class FFV1Writer:
    def __init__(self, path, width, height, fps=20):
        path = Path(path)
        if path.exists() or not path.parent.is_dir() or min(width, height, fps) <= 0:
            raise ValueError('Fresh camera path and positive source profile required')
        self.path, self.width, self.height, self.fps = path, width, height, fps
        self.frames = 0
        self.exit_code = None
        self.process = subprocess.Popen([
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-n',
            '-f', 'rawvideo', '-pixel_format', 'bgra',
            '-video_size', f'{width}x{height}', '-framerate', str(fps),
            '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-level', '3',
            '-pix_fmt', 'bgr0', str(path)], stdin=subprocess.PIPE,
            stderr=subprocess.PIPE)

    def write(self, image):
        if (image.width, image.height) != (self.width, self.height):
            raise ValueError('Original Native camera dimensions differ')
        bgra = bytes(image.raw_data)
        if len(bgra) != self.width * self.height * 4:
            raise ValueError('Incomplete original Native BGRA frame')
        if self.process.poll() is not None:
            raise ValueError('Original camera encoder exited before frame closure')
        self.process.stdin.write(bgra)
        self.frames += 1

    def close(self):
        if self.exit_code is not None:
            return self.exit_code
        if not self.process.stdin.closed:
            self.process.stdin.close()
        try:
            code = self.process.wait(timeout=120)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
            code = self.process.returncode
        error = self.process.stderr.read().decode(errors='replace')
        self.process.stderr.close()
        self.exit_code = code
        if code != 0 or not self.path.is_file():
            raise ValueError('Original FFV1 camera encoder failed: ' + error[-1000:])
        return code

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
