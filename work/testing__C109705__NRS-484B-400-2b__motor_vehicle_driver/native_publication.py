"""Publish source-bound Native rows and videos into a materialized attempt."""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path


CHANNELS = {'dash': 'overview', 'front': 'approach',
            'left': 'reference_corner', 'right': 'driver_reference'}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        if isinstance(value, list):
            for row in value:
                stream.write(json.dumps(row, allow_nan=False) + '\n')
        else:
            stream.write(json.dumps(value, indent=2, allow_nan=False) + '\n')


def project(output, survey):
    """Use only the captured ego, camera and reviewed map packets."""
    output = Path(output)
    trace = json.loads((output / 'original-trace.json').read_text())
    cameras = json.loads((output / 'original-camera-index.json').read_text())['channels']
    samples = trace['samples']
    if len(samples) != 900 or set(cameras) != set(CHANNELS) or any(
            len(cameras[channel]) != 900 for channel in CHANNELS):
        raise ValueError('original Native frame coverage differs')
    first = samples[0]['elapsed_seconds']
    mapping, projected, bodies = [], [], []
    for index, row in enumerate(samples):
        frame, time_s = row['frame'], row['elapsed_seconds']
        if (type(frame) is not int or (index and frame <= samples[index - 1]['frame']) or
                abs(time_s - first - index / 20) > .002):
            raise ValueError('original Native identity or clock differs')
        camera_frames = {}
        for channel in CHANNELS:
            source = cameras[channel][index]
            path = output / source['source_path']
            if (source['frame'] != frame or path.is_symlink() or
                    not path.is_file() or _sha(path) != source['source_sha256']):
                raise ValueError('original camera/frame source differs: ' + channel)
            camera_frames[CHANNELS[channel]] = frame
        mapping.append({'video_frame': index, 'carla_frame': frame,
                        'native_frame': frame, 'time_s': time_s,
                        'camera_frames': camera_frames})
        x, y = row['position_xy_m']
        heading, speed = row['heading_rad'], row['speed_mps']
        projected.append({'frame': frame, 'time_s': time_s,
                          'position': {'x': x, 'y': y, 'z': 0.0},
                          'position_m': [x, y, 0.0],
                          'heading_deg': math.degrees(heading),
                          'speed_mps': speed, 'speed_mph': speed / .44704,
                          'velocity_mps': [speed * math.cos(heading),
                                           speed * math.sin(heading), 0.0],
                          'control': {}, 'road_id': row['road_id']})
        bodies.append({'frame': frame, 'time_s': time_s,
                       'body_vertices_m': [[*point, 0.0] for point in row['body_corners_xy_m']],
                       'road_id': row['road_id']})
    _write_new(output / 'video_frames.jsonl', mapping)
    _write_new(output / 'trace.jsonl', projected)
    _write_new(output / 'body_history.jsonl', bodies)
    region = survey.get('intersection_polygon_xy_m')
    if region is None:
        region = survey.get('phase_regions', {}).get('intersection_entry')
    if not isinstance(region, list) or len(region) < 3:
        raise ValueError('reviewed intersection polygon missing')
    destination = survey.get('destination_direction_xy')
    if destination is None:
        a, b = survey['destination_centerline_xy_m']
        delta = [b[i] - a[i] for i in (0, 1)]
        length = math.hypot(*delta)
        if length <= 0:
            raise ValueError('reviewed destination direction missing')
        destination = [value / length for value in delta]
    _write_new(output / 'road_geometry.json', {
        'intersection_xy_m': region,
        'approach_road_id': survey['approach_road_id'],
        'connector_road_id': survey.get('connector_road_id'),
        'departure_road_id': survey['destination_road_id'],
        'departure_direction_xy': destination,
        'two_way': True,
        'original_survey_sha256': survey['source_sha256'],
    })
    _write_new(output / 'acquisition-provenance.json', {
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'original_trace_sha256': _sha(output / 'original-trace.json'),
        'original_camera_index_sha256': _sha(output / 'original-camera-index.json'),
        'original_map_packet_sha256': _sha(output / 'original-map-packet.json'),
    })
    return len(mapping)


def encode(output):
    """Decode each retained original PNG and losslessly encode all four channels."""
    from PIL import Image
    output = Path(output)
    camera = json.loads((output / 'original-camera-index.json').read_text())['channels']
    dimensions = {'dash': (1920, 1080), 'front': (1280, 720),
                  'left': (1280, 720), 'right': (1280, 720)}
    hashes = {}
    for channel, name in CHANNELS.items():
        target = output / (name + '.mkv')
        if target.exists() or target.is_symlink():
            raise ValueError('refusing to overwrite original camera video')
        command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                   '-f', 'image2pipe', '-framerate', '20', '-vcodec', 'png',
                   '-i', 'pipe:0', '-frames:v', '900', '-an', '-c:v', 'ffv1',
                   '-pix_fmt', 'yuv444p', str(target)]
        process = subprocess.Popen(command, stdin=subprocess.PIPE,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            for source in camera[channel]:
                path = output / source['source_path']
                raw = path.read_bytes()
                if hashlib.sha256(raw).hexdigest() != source['source_sha256']:
                    raise ValueError('original camera PNG changed: ' + channel)
                with Image.open(path) as image:
                    image.load()
                    if image.size != dimensions[channel]:
                        raise ValueError('original camera dimensions differ: ' + channel)
                process.stdin.write(raw)
            process.stdin.close()
            error = process.stderr.read()
            if process.wait() != 0 or not target.is_file() or not target.stat().st_size:
                raise ValueError('original camera encoder failed: ' + channel + ' ' +
                                 error.decode(errors='replace')[-300:])
        except BaseException:
            if process.poll() is None:
                process.kill()
            process.wait()
            raise
        finally:
            process.stderr.close()
        hashes[name] = _sha(target)
    return hashes
