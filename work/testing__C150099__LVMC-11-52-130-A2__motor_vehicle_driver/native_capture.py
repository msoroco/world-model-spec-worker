"""Source-gated 20 Hz original fire-lane acquisition through a Native adapter.

The adapter is injected so CPU tests exercise ordering and failure behavior
without CARLA. Physical sign legibility and lawful designation stay for review.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from fire_lane import CASES, build_case
from source_packet import EXCEPTION_SOURCES, SOURCES, validate_packet
from judgment_sweeps import CONFLICT_POINTS, DESIGNATION_POINTS, preflight as sweep_preflight

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FRAMES = 900


def _write(path: Path, value: dict) -> str:
    data = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def capture(adapter, case_id: str, packet_path: Path, destination: Path,
            after_tick=None, control_profile: str = 'normal') -> dict:
    """Capture a complete original attempt, or remove the partial attempt.

    Adapter methods include get_opendrive_bytes, tick, read_footprint,
    read_activity, read_cameras, read_sign, brake, cleanup, and the construction
    methods used by fire_lane.build_case. Each camera returns a PNG for the same
    Native frame. The adapter controls CARLA lifecycle and actor ownership.
    """
    cases = [case for case in CASES if case_id.endswith('__' + case.id)]
    if len(cases) != 1:
        raise ValueError('unknown exact fire-lane case')
    if after_tick is not None and not callable(after_tick):
        raise ValueError('same-tick graph capture callback invalid')
    if control_profile not in ('normal', 'slow_approach'):
        raise ValueError('unsupported curb approach control profile')
    case = cases[0]
    site = validate_packet(Path(packet_path), case_id)
    if case.sweep_kind != 'none':
        rank = int(case.id.rsplit('-', 1)[1])
        point = (CONFLICT_POINTS if case.sweep_kind == 'conflict_gap'
                 else DESIGNATION_POINTS)[rank]
        sweep_preflight(Path(packet_path), case_id, point,
                        adapter.ego_body_length_m())
    map_bytes = adapter.get_opendrive_bytes()
    if not isinstance(map_bytes, bytes) or hashlib.sha256(map_bytes).hexdigest() != site['map_sha256']:
        raise ValueError('Native map bytes differ from reviewed site')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise ValueError('original attempt destination exists')
    root = Path(tempfile.mkdtemp(prefix='fire-lane-attempt-', dir=destination.parent))
    archives = {}
    started = False
    rows = []
    frames = []
    try:
        packet = json.loads(Path(packet_path).read_text())
        source_dir = root / 'source-review'
        source_dir.mkdir()
        names = list(SOURCES)
        if case.exception != 'none':
            names.append(EXCEPTION_SOURCES[case.exception])
        sealed_packet = dict(packet, sources={})
        for name in names:
            entry = dict(packet['sources'][name])
            original_path = Path(entry['path'])
            if not original_path.is_absolute():
                original_path = Path(packet_path).parent / original_path
            target = source_dir / (name + original_path.suffix)
            raw = original_path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != entry['sha256']:
                raise ValueError('reviewed original source changed during handoff: ' + name)
            target.write_bytes(raw)
            entry['path'] = str(target.relative_to(root))
            sealed_packet['sources'][name] = entry
        site_sha = _write(root / 'reviewed-packet.json', sealed_packet)
        _write(root / 'site.json', site)
        (root / 'road.xodr').write_bytes(map_bytes)
        body_length = adapter.ego_body_length_m()
        built = build_case(adapter, site, case, body_length)
        started = True
        if control_profile == 'slow_approach':
            adapter.set_control_profile(built['ego'], 'slow_approach')
        archives = {name: zipfile.ZipFile(root / (name + '.zip'), 'w', zipfile.ZIP_STORED)
                    for name in CAMERAS}
        previous = None
        for index in range(FRAMES):
            tick = adapter.tick()
            frame, time_s = tick.get('frame'), tick.get('time_s')
            if type(frame) is not int or type(time_s) not in (int, float) or not math.isfinite(time_s):
                raise ValueError('Native frame identity missing')
            if previous is not None and (frame != previous[0] + 1 or
                    not 0.049 <= time_s - previous[1] <= 0.051):
                raise ValueError('Native 20 Hz frame join failed')
            previous = (frame, time_s)
            if after_tick is not None:
                after_tick(frame, time_s)
            footprint = adapter.read_footprint(frame)
            activity = adapter.read_activity(frame)
            sign = adapter.read_sign(built['sign'])
            cameras = adapter.read_cameras(frame)
            if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS):
                raise ValueError('four original camera sources missing')
            if any(packet.get('frame') != frame or packet.get('time_s') != time_s
                   for packet in (footprint, activity)):
                raise ValueError('original body/activity frame join failed')
            camera_frames = {}
            for name in CAMERAS:
                packet = cameras[name]
                raw = packet.get('png')
                if (packet.get('frame') != frame or packet.get('time_s') != time_s or
                        not isinstance(raw, bytes) or not raw.startswith(b'\x89PNG\r\n\x1a\n')):
                    raise ValueError('original camera frame missing: ' + name)
                digest = hashlib.sha256(raw).hexdigest()
                archives[name].writestr(f'{index:04d}-{frame}.png', raw)
                camera_frames[name] = {'original_frame': frame, 'source_sha256': digest}
            row = {key: site[key] for key in (
                'map_sha256', 'jurisdiction_sha256', 'fire_code_designation_sha256',
                'posting_authority_sha256', 'posted_extent_sha256',
                'sign_identity_sha256', 'sign_appearance_sha256',
                'curb_geometry_sha256', 'property_source_sha256',
                'route_sha256', 'weather_sha256',
                'camera_plan_sha256')}
            row.update(case_id=case_id, original_frame=frame, time_s=time_s,
                ego_id=str(built['ego']), sign_id=str(built['sign']),
                site_sha256=site_sha, source_sha256=hashlib.sha256(
                    json.dumps(tick, sort_keys=True).encode()).hexdigest(),
                body_footprint_source_sha256=hashlib.sha256(
                    json.dumps(footprint, sort_keys=True).encode()).hexdigest(),
                sign_physically_present=sign.get('physically_present'),
                sign_text_readback=sign.get('text'),
                body_west_x_m=footprint['west_x_m'],
                body_east_x_m=footprint['east_x_m'],
                body_curb_gap_m=footprint['curb_gap_m'],
                body_interval_m=[footprint['west_x_m'], footprint['east_x_m']],
                posted_interval_m=site['posted_interval_m'],
                activity_observation=activity['state'],
                attended_observation=activity['attended'],
                property_kind=site['property_kind'],
                exception_kind=activity['exception_kind'],
                exception_source_sha256=site.get({
                    'lawful_traffic_conflict': 'traffic_conflict_source_sha256',
                    'police_direction': 'police_direction_source_sha256',
                    'traffic_device_direction': 'traffic_device_source_sha256',
                }.get(case.exception, '')),
                camera_frames=camera_frames)
            if case.sweep_kind == 'posted_offset':
                row['reviewed_posted_end_x_m'] = site['posted_interval_m'][1]
            if case.sweep_kind == 'conflict_gap':
                observed_gap = adapter.read_conflict_gap(frame)
                if (not isinstance(observed_gap, dict) or observed_gap.get('frame') != frame or
                        observed_gap.get('time_s') != time_s or
                        type(observed_gap.get('body_gap_m')) not in (int, float) or
                        not math.isfinite(observed_gap['body_gap_m']) or
                        not observed_gap.get('actor_id')):
                    raise ValueError('original conflict actor gap frame join failed')
                row['actual_actor_body_gap_m'] = observed_gap['body_gap_m']
                row['conflict_actor_id'] = str(observed_gap['actor_id'])
                row['traffic_conflict_source_sha256'] = site['traffic_conflict_source_sha256']
            rows.append(row)
            frames.append({'frame': frame, 'time_s': time_s, 'video_frame': index})
        if hashlib.sha256(adapter.get_opendrive_bytes()).hexdigest() != site['map_sha256']:
            raise ValueError('Native map changed during capture')
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise
    finally:
        for archive in archives.values():
            archive.close()
        try:
            if started:
                adapter.brake()
        finally:
            try:
                adapter.cleanup()
            except BaseException:
                shutil.rmtree(root, ignore_errors=True)
                raise
    try:
        frame_map_sha = _write(root / 'frame_map.json', {'frames': frames})
        for row in rows:
            row['frame_map_sha256'] = frame_map_sha
        history = root / 'history.jsonl'
        history.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
        inventory = {
            'case_id': case_id, 'source_kind': 'original_native',
            'diagnostic_fixture': not bool(getattr(adapter, 'native_attested', False)),
            'site_sha256': site_sha,
            'original_packet_sha256': hashlib.sha256(Path(packet_path).read_bytes()).hexdigest(),
            'history_sha256': hashlib.sha256(history.read_bytes()).hexdigest(),
            'frame_map_sha256': frame_map_sha,
            'camera_media': {name: hashlib.sha256((root / (name + '.zip')).read_bytes()).hexdigest()
                             for name in CAMERAS},
            'physical_completion': False,
            'control_profile': control_profile,
        }
        _write(root / 'inventory.json', inventory)
        os.replace(root, destination)
        return inventory
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise
