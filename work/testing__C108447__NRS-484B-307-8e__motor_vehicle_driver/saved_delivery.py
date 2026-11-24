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

from case_observation import audit_case
from property_route import _traversed_property_ids, analyze_files

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
PROFILE = {'overview': (1920, 1080), 'approach': (1280, 720),
           'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_original_image(image, camera: str, expected_frames: int) -> None:
    """Require the pinned profile for a full production episode."""
    require(image.format == 'PNG' and image.width > 0 and image.height > 0,
            f'{camera} original PNG required')
    if expected_frames == 900:
        require(image.size == PROFILE[camera], f'{camera} original PNG profile required')


def source_file(root: Path, ref: dict, label: str) -> Path:
    require(isinstance(ref, dict) and isinstance(ref.get('path'), str) and isinstance(ref.get('sha256'), str), f'{label} source seal required')
    root = Path(root).resolve()
    declared = Path(ref['path'])
    require('..' not in declared.parts, f'{label} source path traversal forbidden')
    path = root / declared
    resolved = path.resolve()
    require(resolved.is_relative_to(root) and path.is_file(), f'{label} source must be inside original attempt')
    require(not path.is_symlink() and not any(parent.is_symlink() for parent in path.parents if parent != root and parent.is_relative_to(root)),
            f'{label} source symlink alias forbidden')
    require(sha(path.read_bytes()) == ref['sha256'], f'{label} source hash differs')
    return path


def physical_completion(map_packet: dict, trace: dict, case_id: str) -> dict:
    """Measure route completion from original body samples and source route.

    The 1.5 m endpoint radius is the Native controller's engineering arrival
    tolerance. It has no statutory meaning. A claimed entry frame alone cannot
    establish arrival.
    """
    body = trace.get('ego', [])
    entry_frame = trace.get('destination_entry_frame')
    if not body or type(entry_frame) is not int:
        return {'status': 'unverified', 'method': 'original sampled body and source route endpoint',
                'reason': 'body samples or destination entry frame missing', 'observed': {}}
    route = map_packet.get('roadway_route') if case_id.endswith('__ordinary_crossing') else None
    if route is None:
        parcels = map_packet.get('properties', [])
        selected_status = 'public' if case_id.endswith('__public_bypass') else 'private'
        traversed = set(_traversed_property_ids(body, parcels))
        selected = [p['id'] for p in parcels if p.get('status') == selected_status and p.get('id') in traversed]
        if len(selected) != 1:
            return {'status': 'not_met', 'method': 'original sampled body and source route endpoint',
                    'reason': 'one source-classified property was not traversed',
                    'observed': {'traversed_property_ids': sorted(traversed)}}
        route = map_packet.get('connector_routes', {}).get(selected[0])
    if not isinstance(route, list) or len(route) < 3:
        return {'status': 'unverified', 'method': 'original sampled body and source route endpoint',
                'reason': 'source route missing', 'observed': {}}
    entry = next((row for row in body if row.get('frame') == entry_frame), None)
    if entry is None or not all(math.isfinite(float(row.get(key, float('nan')))) for row in (body[0], entry) for key in ('x', 'y')):
        return {'status': 'unverified', 'method': 'original sampled body and source route endpoint',
                'reason': 'finite original body entry sample missing', 'observed': {}}
    start = (float(body[0]['x']), float(body[0]['y']))
    end = (float(entry['x']), float(entry['y']))
    target = (float(route[-1][0]), float(route[-1][1]))
    displacement = math.dist(start, end)
    endpoint_error = math.dist(end, target)
    status = 'met' if entry_frame > body[0]['frame'] and displacement >= 1.0 and endpoint_error <= 1.5 else 'not_met'
    return {'status': status, 'method': 'original sampled body and source route endpoint',
            'reason': None if status == 'met' else 'entry does not reach the source route endpoint after motion',
            'observed': {'start_xy_m': list(start), 'entry_xy_m': list(end),
                         'source_endpoint_xy_m': list(target), 'entry_frame': entry_frame,
                         'displacement_m': displacement, 'endpoint_error_m': endpoint_error,
                         'engineering_endpoint_radius_m': 1.5}}


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
    require(isinstance(authority_data.get('connector_routes'), dict) and authority_data['connector_routes']
            and authority_data['connector_routes'] == map_packet.get('connector_routes'),
            'saved connector route differs from sealed authority')
    require(authority_data.get('roadway_route') == map_packet.get('roadway_route'),
            'saved roadway route differs from sealed authority')
    require(map_packet.get('authority_review', {}).get('decision') == 'reviewed', 'original parcel authority review required')
    require(case.get('case_id') == trace.get('case_id') == bundle['case_id'], 'case identity differs')
    if bundle['case_id'].endswith('__ordinary_crossing'):
        require(isinstance(map_packet.get('roadway_route'), list) and map_packet['roadway_route'],
                'source-bound ordinary roadway route required')
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
            names = archive.namelist()
            require(len(names) == expected_frames and len(set(names)) == expected_frames and
                    set(names) == {item['member'] for item in members},
                    f'{camera} image inventory differs or contains duplicate entries')
            for item in members:
                data = archive.read(item['member'])
                require(sha(data) == item['sha256'], f'{camera} original image hash differs')
                with Image.open(BytesIO(data)) as image:
                    validate_original_image(image, camera, expected_frames)
                    image.load()
        decoded[camera] = len(members)
    observation = analyze_files(map_path, trace_path, case_path)
    case_audit = audit_case(observation, trace, case)
    completion = physical_completion(map_packet, trace, bundle['case_id'])
    require(completion['status'] == 'met', 'original physical route completion required')
    return {'format': 'saved-property-delivery-audit-v1', 'case_id': bundle['case_id'],
            'frame_count': expected_frames, 'decoded_original_images': decoded,
            'observations': observation, 'case_observation_audit': case_audit,
            'physical_completion': completion,
            'physical_acceptance_claimed': False,
            'legal_judgment': None}
