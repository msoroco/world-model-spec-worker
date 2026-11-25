"""Independent exact-case source custody audit for signed-zone captures."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import zipfile
from pathlib import Path

from speed_site import validate_packet

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit(attempt, case_id):
    attempt = Path(attempt).resolve()
    original = attempt / 'original-attempt'
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    if config.get('selected_case_id') != case_id or construction.get('case_id') != case_id:
        raise ValueError('selected speed case identity changed')
    packet, site, case = validate_packet(original / 'site-packet.json', case_id)
    capture_path = original / 'capture.json'
    capture = json.loads(capture_path.read_text())
    seal = json.loads((original / 'capture-source-seal.json').read_text())
    if capture.get('case_id') != case_id or seal.get('case_id') != case_id or \
            seal.get('capture_sha256') != sha(capture_path):
        raise ValueError('original speed capture source seal differs')
    diagnostic = capture.get('diagnostic_fixture') is True
    rows = capture.get('original_rows')
    mapping = json.loads((original / 'frame-map.json').read_text())['frames']
    trace = lines(attempt / 'trace.jsonl')
    video = lines(attempt / 'video_frames.jsonl')
    count = len(rows) if diagnostic and isinstance(rows, list) else 900
    if not (8 <= count <= 20 if diagnostic else count == 900) or not \
            (len(rows) == len(mapping) == len(trace) == len(video) == count):
        raise ValueError('original speed frame count differs')
    packet_sha = sha(original / 'site-packet.json')
    first = rows[0]['original_frame']
    for index, (row, mapped, motion, image) in enumerate(zip(rows, mapping, trace, video)):
        frame = first + index
        t = row['original_time_s']
        if row.get('original_frame') != frame or row.get('source_sha256') != packet_sha or \
                row.get('direction') != case.direction or \
                row.get('sign_readback_source_sha256') != \
                packet['sources'][case.direction + '_sign']['sha256'] or \
                mapped.get('video_frame') != index or mapped.get('original_frame') != frame or \
                mapped.get('time_s') != t or motion.get('original_frame') != frame or \
                motion.get('time_s') != t or image.get('original_frame') != frame or \
                image.get('video_frame') != index or image.get('time_s') != t:
            raise ValueError('original speed time/source join differs')
        if type(row.get('inside_zone')) is not bool or type(row.get('sign_installed')) is not bool or \
                not isinstance(row.get('actual_speed_mps'), (int, float)):
            raise ValueError('original speed observable missing')
    cameras = {}
    for name in VIEWS:
        path = original / (name + '.zip')
        if path.is_file():
            media = path.read_bytes()
        elif diagnostic:
            media = base64.b64decode((original / (name + '.zip.b64')).read_text().strip(),
                                     validate=True)
        else:
            raise ValueError('original speed camera missing: ' + name)
        cameras[name] = hashlib.sha256(media).hexdigest()
        with zipfile.ZipFile(io.BytesIO(media)) as archive:
            if archive.namelist() != [f'{i:04d}.png' for i in range(count)]:
                raise ValueError('original speed camera inventory differs: ' + name)
            for index in range(count):
                raw = archive.read(f'{index:04d}.png')
                if not raw.startswith(b'\x89PNG\r\n\x1a\n') or \
                        hashlib.sha256(raw).hexdigest() != \
                        mapping[index]['camera_frames'][name]['sha256']:
                    raise ValueError('original speed camera pixel source changed: ' + name)
    return {'format': 'worker-speed-original-delivery-audit', 'case_id': case_id,
            'original_frames': count, 'site_packet_sha256': packet_sha,
            'capture_sha256': sha(capture_path), 'camera_sha256': cameras,
            'trace_sha256': sha(attempt / 'trace.jsonl'),
            'video_map_sha256': sha(attempt / 'video_frames.jsonl'),
            'diagnostic_fixture': diagnostic, 'source_custody_passed': True,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}
