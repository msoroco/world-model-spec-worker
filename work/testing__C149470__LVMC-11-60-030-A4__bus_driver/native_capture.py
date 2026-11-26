"""Acquire a source-sealed original bus loading attempt through a Native adapter."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from reviewed_source import FIELDS, construct_reviewed, verify

CAMERAS = ('overview', 'approach', 'curb_wheel', 'traffic')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def capture(adapter, packet_path: Path, case_name: str, destination: Path) -> dict:
    """Record 900 joined 20 Hz frames; remove the attempt after any failure."""
    if getattr(adapter, 'native_attested', False) is not True:
        raise ValueError('attested original Native adapter required')
    reviewed = verify(packet_path, case_name)
    destination = Path(destination)
    if destination.exists():
        raise ValueError('original destination already exists')
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='bus-original-', dir=destination.parent))
    actors = None
    try:
        packet = json.loads(Path(packet_path).read_text())
        source_dir = stage / 'reviewed-sources'
        source_dir.mkdir()
        bindings = {}
        for name in FIELDS:
            binding = dict(packet['source_bindings'][name])
            origin = (Path(packet_path).parent / binding['path']).resolve()
            target = source_dir / (name + origin.suffix)
            target.write_bytes(origin.read_bytes())
            if sha(target) != binding['sha256']:
                raise ValueError('reviewed source changed during capture: ' + name)
            binding['path'] = str(target.relative_to(stage))
            bindings[name] = binding
        packet['source_bindings'] = bindings
        sealed = stage / 'reviewed-site.json'
        sealed.write_text(json.dumps(packet, sort_keys=True) + '\n', encoding='utf-8')
        sealed_review = verify(sealed, case_name)
        actors = construct_reviewed(adapter, sealed, case_name)
        camera_dirs = {name: stage / ('frames-' + name) for name in CAMERAS}
        for folder in camera_dirs.values():
            folder.mkdir()
        rows = []
        previous = None
        for index in range(900):
            snapshot = adapter.tick(actors)
            frame, time_s = snapshot.get('frame'), snapshot.get('time_s')
            if type(frame) is not int or type(time_s) not in (int, float):
                raise ValueError('original Native frame/time missing')
            if previous is not None and (frame != previous[0] + 1 or
                    not .049 <= time_s - previous[1] <= .051):
                raise ValueError('original Native 20 Hz sequence broken')
            previous = frame, time_s
            row = adapter.read_bus_row(frame, actors)
            if row.get('origin') != 'native_world_snapshot' or row.get('original_frame') != frame or row.get('time_s') != time_s:
                raise ValueError('original bus snapshot identity changed')
            row = dict(row)
            row.pop('origin')
            row['case_id'] = sealed_review['scene']['case_id']
            for name in ('right_front_wheel', 'curb_geometry',
                         'location_designation', 'loading_activity'):
                if row.get(name + '_source_sha256') != sealed_review['source_hashes'][name]:
                    raise ValueError('original frame source differs: ' + name)
            cameras = adapter.read_cameras(frame, actors)
            if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS):
                raise ValueError('four original cameras missing')
            for name in CAMERAS:
                camera = cameras[name]
                raw = camera.get('png')
                if camera.get('frame') != frame or camera.get('time_s') != time_s or \
                        not isinstance(raw, bytes) or not raw.startswith(b'\x89PNG\r\n\x1a\n'):
                    raise ValueError('original camera pixel/frame join missing: ' + name)
                (camera_dirs[name] / f'{index:04d}.png').write_bytes(raw)
            rows.append(row)
        rows_path = stage / 'original-bus-frames.jsonl'
        rows_path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows),
                             encoding='utf-8')
        cameras = {}
        for name, folder in camera_dirs.items():
            video = stage / (name + '.mkv')
            command = ['ffmpeg', '-v', 'error', '-nostdin', '-framerate', '20',
                       '-i', str(folder / '%04d.png'), '-frames:v', '900',
                       '-c:v', 'ffv1', str(video)]
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL,
                           stderr=subprocess.PIPE)
            cameras[name] = {'path': video.name, 'sha256': sha(video), 'frame_count': 900}
            shutil.rmtree(folder)
        identity = {'case_id': sealed_review['scene']['case_id'],
                    'source_kind': 'original_native_capture', 'diagnostic_fixture': False,
                    'reviewed_site_sha256': sha(sealed), 'frames_sha256': sha(rows_path),
                    'cameras': cameras, 'legal_status': 'unresolved',
                    'physical_acceptance': False}
        (stage / 'capture-identity.json').write_text(json.dumps(identity, sort_keys=True) + '\n',
                                                     encoding='utf-8')
        os.replace(stage, destination)
        return identity
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    finally:
        try:
            adapter.brake()
        finally:
            try:
                if actors is not None:
                    for actor in reversed(actors['owned']):
                        adapter.destroy(actor)
            finally:
                adapter.restore()
