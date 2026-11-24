"""CARLA-lazy four-view original camera recorder for straight-green attempts."""
from __future__ import annotations

import hashlib
import io
import subprocess
from pathlib import Path
from queue import Empty, Queue

from PIL import Image

from delivery_audit import PRODUCTION_PROFILE, VIEWS


class OriginalCameraRecorder:
    def __init__(self, sensors: dict, scratch: Path, *,
                 profile: dict = PRODUCTION_PROFILE, expected_frames: int = 900,
                 diagnostic_fixture: bool = False, timeout_s: float = 5.0):
        if set(sensors) != set(VIEWS) or set(profile) != set(VIEWS):
            raise ValueError('four original camera sensors and profile required')
        if profile != PRODUCTION_PROFILE and not diagnostic_fixture:
            raise ValueError('profile override requires diagnostic fixture')
        if expected_frames < 2 or timeout_s <= 0:
            raise ValueError('valid original frame count and timeout required')
        self.sensors = sensors
        self.profile = profile
        self.expected_frames = expected_frames
        self.timeout_s = timeout_s
        self.scratch = Path(scratch)
        if not self.scratch.is_dir() or any((self.scratch / view).exists() for view in VIEWS):
            raise ValueError('fresh camera scratch directory required')
        self.queues = {view: Queue(maxsize=expected_frames + 2) for view in VIEWS}
        self.count = 0
        self.closed = False
        for view in VIEWS:
            (self.scratch / view).mkdir()
            sensors[view].listen(lambda image, view=view: self.queues[view].put_nowait(image))

    def read(self, snapshot) -> dict:
        if self.closed or self.count >= self.expected_frames:
            raise ValueError('original camera recorder closed or complete')
        frame = snapshot.frame
        pending = {}
        for view in VIEWS:
            try:
                image = self.queues[view].get(timeout=self.timeout_s)
            except Empty as exc:
                raise ValueError('original camera callback missing: ' + view) from exc
            width, height = self.profile[view]
            if image.frame != frame or image.width != width or image.height != height:
                raise ValueError('original camera frame or dimensions differ: ' + view)
            raw = bytes(image.raw_data)
            if len(raw) != width * height * 4:
                raise ValueError('original camera BGRA buffer differs: ' + view)
            output = io.BytesIO()
            Image.frombytes('RGBA', (width, height), raw, 'raw', 'BGRA').convert('RGB').save(
                output, format='PNG')
            pending[view] = output.getvalue()
        for view, image_bytes in pending.items():
            (self.scratch / view / f'{self.count:06d}.png').write_bytes(image_bytes)
        self.count += 1
        return {view: frame for view in VIEWS}

    def finish(self, output: Path) -> dict:
        """Encode four lossless 20 Hz originals; return attempt-relative seals."""
        if self.closed or self.count != self.expected_frames:
            raise ValueError('complete original camera callbacks required')
        output = Path(output)
        if not output.is_dir() or any((output / f'{view}.mkv').exists() for view in VIEWS):
            raise ValueError('fresh original camera output required')
        refs = {}
        created = []
        try:
            for view in VIEWS:
                path = output / f'{view}.mkv'
                result = subprocess.run(
                    ['ffmpeg', '-v', 'error', '-xerror', '-framerate', '20',
                     '-i', str(self.scratch / view / '%06d.png'),
                     '-frames:v', str(self.expected_frames), '-c:v', 'ffv1',
                     '-level', '3', str(path)], capture_output=True, text=True)
                if result.returncode or not path.is_file() or path.stat().st_size == 0:
                    raise ValueError('original camera lossless encode failed: ' + view + ' ' + result.stderr[-200:])
                created.append(path)
                refs[view] = {'path': path.name,
                              'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            return refs
        except Exception:
            for path in created:
                path.unlink(missing_ok=True)
            raise

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            for sensor in self.sensors.values():
                sensor.stop()
