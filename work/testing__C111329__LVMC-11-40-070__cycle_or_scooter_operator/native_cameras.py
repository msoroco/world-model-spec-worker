"""Four original camera archives bound to each Native bicycle instruction tick."""
from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZIP_STORED

from PIL import Image

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
DIMENSIONS = {'overview': (1920, 1080), 'approach': (1280, 720),
              'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


class FourCameraCapture:
    def __init__(self, root, readers, dimensions=None):
        if set(readers) != set(CAMERAS):
            raise ValueError('four named original camera readers required')
        self.root = Path(root)
        self.dimensions = dimensions or DIMENSIONS
        if set(self.dimensions) != set(CAMERAS):
            raise ValueError('four named camera dimensions required')
        self.readers = readers
        self.archives = {}
        self.paths = {name: self.root / (name + '.png.zip') for name in CAMERAS}
        if any(path.exists() for path in self.paths.values()):
            raise ValueError('original camera archive already exists')
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            for name, path in self.paths.items():
                self.archives[name] = ZipFile(path, 'x', compression=ZIP_STORED)
        except Exception:
            self.abort()
            raise
        self.count = 0

    def sample(self, row):
        frame = row['frame']
        if type(frame) is not int or frame < 0:
            raise ValueError('invalid original camera frame')
        bindings = {}
        for name in CAMERAS:
            sample = self.readers[name](frame)
            if not isinstance(sample, dict) or sample.get('frame') != frame:
                raise ValueError('original camera frame identity mismatch: ' + name)
            payload = sample.get('png_bytes')
            if not isinstance(payload, bytes) or not payload.startswith(b'\x89PNG\r\n\x1a\n'):
                raise ValueError('original camera PNG unavailable: ' + name)
            with Image.open(BytesIO(payload)) as image:
                image.verify()
            with Image.open(BytesIO(payload)) as image:
                if image.format != 'PNG' or image.size != tuple(self.dimensions[name]):
                    raise ValueError('original camera format or dimensions differ: ' + name)
                image.load()
            member = f'{frame:08d}.png'
            self.archives[name].writestr(member, payload)
            bindings[name] = {'member': member, 'sha256': sha_bytes(payload)}
        row['camera_frames'] = bindings
        self.count += 1

    def finish(self):
        for archive in self.archives.values():
            archive.close()
        self.archives.clear()
        return {name: {'path': path.name, 'sha256': sha_bytes(path.read_bytes()),
                       'frame_count': self.count, 'dimensions': list(self.dimensions[name])}
                for name, path in self.paths.items()}

    def abort(self):
        for archive in self.archives.values():
            archive.close()
        self.archives.clear()
        for path in self.paths.values():
            path.unlink(missing_ok=True)
