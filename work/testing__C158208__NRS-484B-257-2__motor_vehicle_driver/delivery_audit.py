"""Independent original source/frame custody audit for one selected yield case."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import zipfile
from pathlib import Path

from yield_site import validate_site


VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit(attempt: Path, expected_case: str):
    attempt = Path(attempt).resolve()
    original = attempt / 'original-attempt'
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    inventory = json.loads((original / 'inventory.json').read_text())
    if config['selected_case_id'] != expected_case or construction['case_id'] != expected_case or \
            inventory['case_id'] != expected_case:
        raise ValueError('original yield delivery case identity differs')
    site = validate_site(original / 'site-packet.json', expected_case)
    source_paths = {'site-packet.json': inventory['site_sha256'],
                    'history.jsonl': inventory['history_sha256'],
                    'frame-map.json': inventory['frame_map_sha256']}
    for relative, expected in source_paths.items():
        if sha(original / relative) != expected:
            raise ValueError('sealed original yield source changed: ' + relative)
    history = rows(original / 'history.jsonl')
    mapping = json.loads((original / 'frame-map.json').read_text())['frames']
    trace = rows(attempt / 'trace.jsonl')
    video = rows(attempt / 'video_frames.jsonl')
    diagnostic = inventory.get('diagnostic_fixture') is True
    if not (len(history) == len(mapping) == len(trace) == len(video)) or \
            (len(history) != config['frame_count'] and not (diagnostic and 8 <= len(history) <= 20)):
        raise ValueError('original yield delivery frame counts differ')
    for index, (row, mapped, motion, image) in enumerate(zip(history, mapping, trace, video)):
        frame = row.get('original_frame')
        time_s = row.get('time_s')
        if row.get('case_id') != expected_case or row.get('source_packet_sha256') != inventory['site_sha256']:
            raise ValueError('original yield case/source differs')
        expected = {'video_frame': index, 'frame': frame, 'time_s': time_s}
        if mapped != expected or motion.get('frame') != frame or \
                motion.get('time_s') != time_s or image.get('video_frame') != index or \
                image.get('carla_frame') != frame or image.get('time_s') != time_s:
            raise ValueError('original yield trace/video frame join differs')
        state = row.get('native_state', {})
        if state.get('other_obligated_to_stop_or_yield') is not False or \
                state.get('officer_controls') is not False or \
                state.get('signal_controls') is not False:
            raise ValueError('original yield governing context changed')
    for camera in VIEWS:
        path = original / (camera + '.zip')
        if path.is_file():
            media = path.read_bytes()
        elif diagnostic:
            media = base64.b64decode((original / (camera + '.zip.b64')).read_text().strip(),
                                     validate=True)
        else:
            raise ValueError('original yield camera missing: ' + camera)
        if hashlib.sha256(media).hexdigest() != inventory['camera_media_sha256'][camera]:
            raise ValueError('sealed original yield camera changed: ' + camera)
        source_paths[camera + '.zip'] = inventory['camera_media_sha256'][camera]
        with zipfile.ZipFile(io.BytesIO(media)) as archive:
            expected = [f'{index:04d}-{row["original_frame"]}.png'
                        for index, row in enumerate(history)]
            if archive.namelist() != expected:
                raise ValueError('original yield camera frames differ: ' + camera)
            for row, member in zip(history, expected):
                raw = archive.read(member)
                if not raw.startswith(b'\x89PNG\r\n\x1a\n') or \
                        hashlib.sha256(raw).hexdigest() != row['camera_frames'][camera]['source_sha256']:
                    raise ValueError('original yield camera PNG changed: ' + camera)
    return {'format': 'worker-yield-original-delivery-audit',
            'case_id': expected_case, 'original_frames': len(history),
            'original_source_sha256': source_paths,
            'trace_sha256': sha(attempt / 'trace.jsonl'),
            'video_map_sha256': sha(attempt / 'video_frames.jsonl'),
            'non_through_highway': site['non_through_highway'],
            'other_obligated_to_stop_or_yield': site['other_obligated_to_stop_or_yield'],
            'diagnostic_fixture': diagnostic, 'source_custody_passed': True,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}
