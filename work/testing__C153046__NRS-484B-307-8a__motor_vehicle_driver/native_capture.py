"""Original 20 Hz source-gated red-left capture through an injected Native adapter."""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from native_setup import create
from red_left_controller import RedLeftController
from red_left_measurement import validate_site, _dot, _xy

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(adapter, config: dict, packet_path: Path, destination: Path) -> dict:
    """Capture 900 original snapshots or remove the incomplete destination."""
    case = config['selected_case_id']
    variables = config['case']['draft_variables']
    packet_path = Path(packet_path).resolve()
    site = validate_site(packet_path, variables['receiving_direction'])
    packet = json.loads(packet_path.read_text())
    if hashlib.sha256(adapter.get_opendrive_bytes()).hexdigest() != site['source_hashes']['opendrive']:
        raise ValueError('Native OpenDRIVE differs from reviewed source')
    destination = Path(destination)
    if destination.exists():
        raise ValueError('original destination exists')
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='red-left-original-', dir=destination.parent))
    archives = {}
    actors = None
    rows = []
    frame_map = []
    try:
        source_dir = stage / 'source-review'
        source_dir.mkdir()
        sealed = dict(packet, sources={})
        for name, source in packet['sources'].items():
            origin = (packet_path.parent / source['path']).resolve()
            raw = origin.read_bytes()
            if hashlib.sha256(raw).hexdigest() != source['sha256']:
                raise ValueError('reviewed site source changed: ' + name)
            target = source_dir / (name + origin.suffix)
            target.write_bytes(raw)
            sealed['sources'][name] = dict(source, path=str(target.relative_to(stage)))
        (stage / 'site-packet.json').write_text(json.dumps(sealed, sort_keys=True) + '\n')
        site_sha = sha(stage / 'site-packet.json')
        actors = create(adapter.world, packet_path, adapter.transform_factory, variables)
        controller = RedLeftController(case, variables, site,
                                       config.get('control', {}).get('approach_hold_margin_m', 1.0))
        archives = {name: zipfile.ZipFile(stage / (name + '.zip'), 'w', zipfile.ZIP_STORED)
                    for name in CAMERAS}
        previous = None
        for index in range(900):
            snapshot = adapter.tick(actors)
            frame, time_s = snapshot.get('frame'), snapshot.get('time_s')
            if type(frame) is not int or type(time_s) not in (int, float) or not math.isfinite(time_s):
                raise ValueError('Native original frame identity missing')
            if previous is not None and (frame != previous[0] + 1 or
                    not 0.049 <= time_s - previous[1] <= 0.051):
                raise ValueError('Native original 20 Hz sequence broken')
            previous = (frame, time_s)
            native = adapter.read_original_frame(frame, actors)
            if native.get('origin') != 'native_world_snapshot' or native.get('frame') != frame or \
                    native.get('time_s') != time_s:
                raise ValueError('original snapshot/frame join differs')
            ego = native.get('ego', {})
            vertices = ego.get('body_vertices_xy', [])
            if len(vertices) < 4:
                raise ValueError('original full-body vertices missing')
            front = max(_dot(tuple(_xy(point, 'ego body')[i] - site['reference'][i]
                                   for i in (0, 1)), site['direction']) for point in vertices)
            observation = {'origin': 'native_world_snapshot',
                           'source_packet_sha256': site['source_packet_sha256'],
                           'signal_actor_id': native.get('signal_actor_id'),
                           'signal_state': native.get('signal_state'),
                           'frame': frame, 'time_s': time_s,
                           'ego_lane_id': ego.get('lane_id'),
                           'body_front_to_stop_m': site['stop_progress_m'] - front,
                           'speed_m_s': ego.get('speed_m_s'),
                           'directed_participants': native.get('directed_participants')}
            request = controller.step(observation)
            cameras = adapter.read_cameras(frame, actors)
            if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS):
                raise ValueError('four original cameras missing')
            camera_frames = {}
            for name in CAMERAS:
                packet_frame = cameras[name]
                raw = packet_frame.get('png')
                if packet_frame.get('frame') != frame or packet_frame.get('time_s') != time_s or \
                        not isinstance(raw, bytes) or not raw.startswith(b'\x89PNG\r\n\x1a\n'):
                    raise ValueError('original camera/frame missing: ' + name)
                archives[name].writestr(f'{index:04d}-{frame}.png', raw)
                camera_frames[name] = {'original_frame': frame,
                                       'source_sha256': hashlib.sha256(raw).hexdigest()}
            rows.append({'case_id': case, 'source_packet_sha256': site_sha,
                         'native_frame': native, 'control_request': request,
                         'camera_frames': camera_frames})
            frame_map.append({'video_frame': index, 'frame': frame, 'time_s': time_s})
            adapter.apply_request(request, actors)
        if hashlib.sha256(adapter.get_opendrive_bytes()).hexdigest() != site['source_hashes']['opendrive']:
            raise ValueError('Native OpenDRIVE changed during capture')
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    finally:
        for archive in archives.values():
            archive.close()
        try:
            adapter.brake()
        finally:
            try:
                if actors is not None:
                    actors.close()
            finally:
                adapter.restore()
    try:
        history = stage / 'history.jsonl'
        history.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
        (stage / 'frame-map.json').write_text(json.dumps({'frames': frame_map}, sort_keys=True) + '\n')
        receipt = {'case_id': case, 'site_sha256': site_sha, 'history_sha256': sha(history),
                   'frame_map_sha256': sha(stage / 'frame-map.json'),
                   'camera_media_sha256': {name: sha(stage / (name + '.zip')) for name in CAMERAS},
                   'original_frames': len(rows), 'diagnostic_fixture':
                   not bool(getattr(adapter, 'native_attested', False)),
                   'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}
        (stage / 'inventory.json').write_text(json.dumps(receipt, sort_keys=True) + '\n')
        os.replace(stage, destination)
        return receipt
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
