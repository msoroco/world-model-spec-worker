"""Independent source and full-pixel audit of original bicycle camera archives."""
from __future__ import annotations

import hashlib
import json
import math
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from PIL import Image

from native_cameras import CAMERAS
from saved_instruction import FORMAT, FRAME_COUNT


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(trace_path, expected_sha256, case_id):
    path = Path(trace_path).resolve()
    if sha(path) != expected_sha256:
        raise ValueError('original instruction source hash mismatch')
    packet = json.loads(path.read_text())
    if packet.get('format') != FORMAT or packet.get('case_id') != case_id:
        raise ValueError('wrong original instruction source or case')
    if packet.get('source_kind') != 'original_native' or packet.get('camera_capture_complete') is not True:
        raise ValueError('original four-camera capture missing')
    rows = packet.get('samples')
    if not isinstance(rows, list) or len(rows) != FRAME_COUNT:
        raise ValueError('incomplete original frame history')
    for index, row in enumerate(rows):
        time = row.get('time_s')
        if (type(row.get('frame')) is not int or type(time) not in (int, float)
                or not math.isfinite(time)):
            raise ValueError('original frame or time unavailable')
        if index and (row['frame'] != rows[index - 1]['frame'] + 1 or
                      not 0.04 <= row['time_s'] - rows[index - 1]['time_s'] <= 0.06):
            raise ValueError('original camera frame or time gap')
    sources = packet.get('camera_sources')
    if not isinstance(sources, dict) or set(sources) != set(CAMERAS):
        raise ValueError('four original camera sources missing')
    for name in CAMERAS:
        ref = sources[name]
        video = (path.parent / ref['path']).resolve()
        if video.parent != path.parent or not video.is_file() or sha(video) != ref['sha256']:
            raise ValueError('original camera source hash mismatch: ' + name)
        if ref.get('frame_count') != len(rows):
            raise ValueError('original camera count mismatch: ' + name)
        expected_members = [f"{row['frame']:08d}.png" for row in rows]
        with ZipFile(video) as archive:
            if archive.namelist() != expected_members:
                raise ValueError('original camera frame map mismatch: ' + name)
            for row, member in zip(rows, expected_members):
                binding = row.get('camera_frames', {}).get(name)
                payload = archive.read(member)
                if binding != {'member': member,
                               'sha256': hashlib.sha256(payload).hexdigest()}:
                    raise ValueError('original camera pixel binding mismatch: ' + name)
                with Image.open(BytesIO(payload)) as image:
                    image.verify()
                with Image.open(BytesIO(payload)) as image:
                    if image.format != 'PNG' or list(image.size) != ref['dimensions']:
                        raise ValueError('original camera image dimensions mismatch: ' + name)
                    image.load()
    return {'format': 'c111329-original-camera-audit', 'case_id': case_id,
            'trace_sha256': expected_sha256, 'decoded_frames': len(rows),
            'decoded_images': len(rows) * len(CAMERAS),
            'physical_acceptance': False, 'legal_assessment': 'unresolved'}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--trace', required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(audit(args.trace, args.sha256, args.case), indent=2) + '\n')
