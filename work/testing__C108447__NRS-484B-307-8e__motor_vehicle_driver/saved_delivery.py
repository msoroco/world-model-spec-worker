"""Independent saved-source audit for the property-bypass Native capture.

The caller supplies original attempt files. This audits retained data and pixels;
it does not decide whether a maneuver was physically or legally successful.
"""
from __future__ import annotations

import hashlib
import json
import math
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from PIL import Image

from property_route import analyze_files

CAMERAS = ('overview', 'approach', 'property', 'destination')


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_file(root: Path, ref: dict, label: str) -> Path:
    require(isinstance(ref, dict) and isinstance(ref.get('path'), str) and isinstance(ref.get('sha256'), str), f'{label} source seal required')
    path = (root / ref['path']).resolve()
    require(path.is_relative_to(root.resolve()) and path.is_file(), f'{label} source must be inside original attempt')
    require(sha(path.read_bytes()) == ref['sha256'], f'{label} source hash differs')
    return path


def audit(attempt: Path, bundle: dict, *, expected_frames: int = 900) -> dict:
    """Check original files, exact frame joins, and every PNG pixel stream."""
    require(expected_frames >= 20, 'bounded source episode required')
    require(bundle.get('format') == 'original-native-property-delivery-v1', 'original delivery bundle required')
    require(bundle.get('case_id'), 'exact case identity required')
    require(bundle.get('diagnostic_fixture') is False, 'diagnostic source cannot establish delivery')
    map_path = source_file(attempt, bundle.get('map'), 'map')
    trace_path = source_file(attempt, bundle.get('trace'), 'trace')
    case_path = source_file(attempt, bundle.get('case'), 'case')
    frame_path = source_file(attempt, bundle.get('frame_map'), 'frame map')
    case = json.loads(case_path.read_text())
    trace = json.loads(trace_path.read_text())
    map_packet = json.loads(map_path.read_text())
    native = map_packet.get('native_map', {})
    native_path = source_file(attempt, native, 'original OpenDRIVE')
    authority = map_packet.get('source', {})
    authority_path = source_file(attempt, authority, 'original parcel authority')
    authority_data = json.loads(authority_path.read_text())
    require(authority_data.get('opendrive_sha256') == sha(native_path.read_bytes()), 'parcel authority original map seal differs')
    require(map_packet.get('authority_review', {}).get('decision') == 'reviewed', 'original parcel authority review required')
    require(case.get('case_id') == trace.get('case_id') == bundle['case_id'], 'case identity differs')
    frames = [json.loads(line) for line in frame_path.read_text().splitlines() if line.strip()]
    body = trace.get('ego', [])
    require(len(body) == len(frames) == expected_frames, 'exact original frame count required')
    frame_ids = [row.get('frame') for row in frames]
    require(all(type(f) is int for f in frame_ids) and all(b == a + 1 for a, b in zip(frame_ids, frame_ids[1:])), 'contiguous original frame map required')
    require([row.get('frame') for row in body] == frame_ids, 'body and original frame map differ')
    require(all(type(row.get('time_s')) in (int, float) and math.isfinite(row['time_s']) for row in frames), 'finite original frame times required')
    require(all(type(row.get('time_s')) in (int, float) and abs(row['time_s'] - frames[i]['time_s']) < 0.002 for i, row in enumerate(body)), 'body and original frame times differ')
    require(all(abs((b['time_s'] - a['time_s']) - 0.05) < 0.002 for a, b in zip(frames, frames[1:])), '20 Hz original frame timing required')
    require(all(row.get('frame') == frame_ids[i] for i, row in enumerate(trace.get('approach_signal_history', []))) and len(trace.get('approach_signal_history', [])) == expected_frames, 'approach signal frame join required')
    require(all(row.get('frame') == frame_ids[i] for i, row in enumerate(trace.get('destination_signal_history', []))) and len(trace.get('destination_signal_history', [])) == expected_frames, 'destination signal frame join required')
    archives = bundle.get('cameras', {})
    require(isinstance(archives, dict) and set(archives) == set(CAMERAS), 'four original camera sources required')
    decoded = {}
    for camera in CAMERAS:
        ref = archives[camera]
        archive_path = source_file(attempt, ref, camera)
        members = ref.get('frames', [])
        require(len(members) == expected_frames, f'{camera} exact image count required')
        require([item.get('frame') for item in members] == frame_ids, f'{camera} frame join required')
        require(all(isinstance(item.get('member'), str) and isinstance(item.get('sha256'), str) for item in members), f'{camera} member seals required')
        require(len({item['member'] for item in members}) == expected_frames, f'{camera} duplicate image member')
        require(all(row.get('cameras', {}).get(camera) == {'member': item['member'], 'sha256': item['sha256']}
                    for row, item in zip(frames, members)), f'{camera} original frame map image join required')
        with ZipFile(archive_path) as archive:
            require(set(archive.namelist()) == {item['member'] for item in members}, f'{camera} image inventory differs')
            for item in members:
                data = archive.read(item['member'])
                require(sha(data) == item['sha256'], f'{camera} original image hash differs')
                with Image.open(BytesIO(data)) as image:
                    require(image.format == 'PNG' and image.width > 0 and image.height > 0, f'{camera} original PNG required')
                    image.load()
        decoded[camera] = len(members)
    observation = analyze_files(map_path, trace_path, case_path)
    return {'format': 'saved-property-delivery-audit-v1', 'case_id': bundle['case_id'],
            'frame_count': expected_frames, 'decoded_original_images': decoded,
            'observations': observation, 'physical_acceptance_claimed': False,
            'legal_judgment': None}
