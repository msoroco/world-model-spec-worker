"""Independently audit one original red-left attempt's source and frame custody."""
from __future__ import annotations

import hashlib
import base64
import io
import json
import zipfile
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit(attempt: Path, expected_case: str) -> dict:
    attempt = Path(attempt).resolve()
    original = attempt / 'original-attempt'
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    inventory = json.loads((original / 'inventory.json').read_text())
    if config['selected_case_id'] != expected_case or construction['case_id'] != expected_case or \
            inventory['case_id'] != expected_case:
        raise ValueError('original delivery case identity differs')
    source_paths = {'site-packet.json': inventory['site_sha256'],
                    'history.jsonl': inventory['history_sha256'],
                    'frame-map.json': inventory['frame_map_sha256']}
    for relative, expected in source_paths.items():
        if sha(original / relative) != expected:
            raise ValueError('sealed original source changed: ' + relative)
    history = rows(original / 'history.jsonl')
    mapping = json.loads((original / 'frame-map.json').read_text())['frames']
    trace = rows(attempt / 'trace.jsonl')
    video = rows(attempt / 'video_frames.jsonl')
    if len(history) != len(mapping) or len(history) != len(trace) or len(history) != len(video):
        raise ValueError('original delivery frame counts differ')
    if len(history) != config['frame_count'] and not (inventory.get('diagnostic_fixture') is True
                                                   and 2 <= len(history) <= 20):
        raise ValueError('original delivery duration differs')
    for index, (row, mapped, motion, image) in enumerate(zip(history, mapping, trace, video)):
        native = row['native_frame']
        if row['case_id'] != expected_case or row['source_packet_sha256'] != inventory['site_sha256']:
            raise ValueError('original delivery case/source differs')
        expected = {'video_frame': index, 'frame': native['frame'], 'time_s': native['time_s']}
        if mapped != expected or motion.get('frame') != native['frame'] or \
                motion.get('time_s') != native['time_s'] or \
                image.get('video_frame') != index or image.get('carla_frame') != native['frame'] or \
                image.get('time_s') != native['time_s']:
            raise ValueError('original delivery frame join differs')
    for camera in CAMERAS:
        archive = original / (camera + '.zip')
        if archive.is_file():
            archive_bytes = archive.read_bytes()
        elif inventory.get('diagnostic_fixture') is True:
            archive_bytes = base64.b64decode(
                (original / (camera + '.zip.b64')).read_text().strip(), validate=True)
        else:
            raise ValueError('missing original camera archive: ' + camera)
        if hashlib.sha256(archive_bytes).hexdigest() != inventory['camera_media_sha256'][camera]:
            raise ValueError('sealed original camera changed: ' + camera)
        source_paths[camera + '.zip'] = inventory['camera_media_sha256'][camera]
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as stream:
            expected_names = [f'{index:04d}-{row["native_frame"]["frame"]}.png'
                              for index, row in enumerate(history)]
            if stream.namelist() != expected_names:
                raise ValueError('original delivery camera frames differ: ' + camera)
            for row, name in zip(history, expected_names):
                raw = stream.read(name)
                if not raw.startswith(b'\x89PNG\r\n\x1a\n') or hashlib.sha256(raw).hexdigest() != \
                        row['camera_frames'][camera]['source_sha256']:
                    raise ValueError('original delivery camera source differs: ' + camera)
    return {'format': 'worker-red-left-original-delivery-audit', 'case_id': expected_case,
            'original_frames': len(history), 'original_source_sha256': source_paths,
            'trace_sha256': sha(attempt / 'trace.jsonl'),
            'video_map_sha256': sha(attempt / 'video_frames.jsonl'),
            'diagnostic_fixture': inventory.get('diagnostic_fixture') is True,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
            'source_custody_passed': True}
