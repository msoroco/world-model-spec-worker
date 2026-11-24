"""Record four original Native camera frames on the event tick timebase."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess


VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


class CameraCaptureError(ValueError):
    pass


class FourViewRecorder:
    """The adapter returns BGRA bytes from sensors synchronized to each tick.

    The operator-owned camera adapter must implement ``read_views(frame)`` and
    return one frame for each view. No authored image or duplicate is accepted.
    """

    def __init__(self, attempt, adapter, case_id):
        self.attempt = Path(attempt)
        self.adapter = adapter
        self.case_id = case_id
        self.processes = {}
        self.dimensions = {}
        self.first = None
        self.last = None
        self.count = 0
        for name in VIEWS:
            if (self.attempt / (name + '.mkv')).exists():
                raise CameraCaptureError('camera output already exists')

    def _start(self, name, width, height):
        output = self.attempt / (name + '.mkv')
        command = ['ffmpeg', '-v', 'error', '-xerror', '-f', 'rawvideo',
                   '-pixel_format', 'bgra', '-video_size', f'{width}x{height}',
                   '-framerate', '20', '-i', 'pipe:0', '-an', '-c:v', 'ffv1',
                   '-level', '3', '-y', str(output)]
        self.processes[name] = subprocess.Popen(command, stdin=subprocess.PIPE,
                                                stdout=subprocess.DEVNULL,
                                                stderr=subprocess.PIPE)
        self.dimensions[name] = (width, height)

    def record(self, event):
        frame = event['frame']
        if self.last is not None and frame != self.last + 1:
            raise CameraCaptureError('camera/event frame gap')
        if self.first is None:
            self.first = frame
        views = self.adapter.read_views(frame)
        if not isinstance(views, dict) or set(views) != set(VIEWS):
            raise CameraCaptureError('four original camera views required')
        sensor_ids = [views[name].get('sensor_id') for name in VIEWS]
        if any(not isinstance(value, str) or not value for value in sensor_ids) or len(set(sensor_ids)) != 4:
            raise CameraCaptureError('four distinct Native camera sensors required')
        for name in VIEWS:
            item = views[name]
            if not isinstance(item, dict) or item.get('source_kind') != 'native_camera_sensor':
                raise CameraCaptureError('non-Native camera frame')
            if item.get('frame') != frame:
                raise CameraCaptureError('camera/event frame mismatch')
            width, height = item.get('width'), item.get('height')
            pixels = item.get('bgra')
            if (not isinstance(width, int) or not isinstance(height, int) or
                    width < 16 or height < 16 or not isinstance(pixels, bytes) or
                    len(pixels) != width * height * 4):
                raise CameraCaptureError('invalid original BGRA camera frame')
            if name not in self.processes:
                self._start(name, width, height)
            elif self.dimensions[name] != (width, height):
                raise CameraCaptureError('camera dimensions drifted')
            try:
                self.processes[name].stdin.write(pixels)
            except (BrokenPipeError, OSError) as exc:
                raise CameraCaptureError('lossless camera encoder failed') from exc
        self.last = frame
        self.count += 1

    def finish(self):
        if self.count != 900 or set(self.processes) != set(VIEWS):
            raise CameraCaptureError('45 second four-view capture incomplete')
        self._close(check=True)
        views = {}
        for name in VIEWS:
            path = self.attempt / (name + '.mkv')
            width, height = self.dimensions[name]
            views[name] = {'source': {'path': path.name,
                                      'sha256': hashlib.sha256(path.read_bytes()).hexdigest()},
                           'width': width, 'height': height,
                           'first_original_frame': self.first,
                           'last_original_frame': self.last}
        manifest = {'case_id': self.case_id, 'fps': 20, 'duration_frames': self.count,
                    'camera_views': views, 'pixel_review_status': 'pending'}
        path = self.attempt / 'media-manifest.json'
        data = (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode()
        path.write_bytes(data)
        return {'path': path.name, 'sha256': hashlib.sha256(data).hexdigest()}

    def _close(self, *, check=False):
        failures = []
        for name, process in self.processes.items():
            if process.stdin and not process.stdin.closed:
                try:
                    process.stdin.close()
                except BrokenPipeError:
                    pass
            stderr = process.stderr.read() if process.stderr else b''
            if process.stderr:
                process.stderr.close()
            code = process.wait()
            if code:
                failures.append(f'{name}: {stderr.decode(errors="replace")[:200]}')
        if check and failures:
            raise CameraCaptureError('lossless camera encoder failed: ' + '; '.join(failures))

    def abort(self):
        for process in self.processes.values():
            if process.poll() is None:
                process.kill()
        self._close()
        for name in VIEWS:
            (self.attempt / (name + '.mkv')).unlink(missing_ok=True)
