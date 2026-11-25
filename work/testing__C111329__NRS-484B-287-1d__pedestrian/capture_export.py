"""Publish sealed original crossing frames to the Native/Core source layout.

The supplied packet is immutable. Exported JSONL and FFV1 files are derived
once from source-hashed original frames after the operator verifies restoration.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path

from native_acquisition import CAMERAS, _sha
from saved_media_audit import audit_camera_sources, PROFILE_DIMENSIONS


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, sort_keys=True, allow_nan=False)
        stream.write('\n')


def lines(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n')


def encode_camera(root, packet, camera, *, diagnostic=False):
    if camera not in CAMERAS:
        raise ValueError('unknown original camera')
    root = Path(root).resolve(strict=True)
    output = root / (camera + '.mkv')
    if output.exists():
        raise ValueError('original camera video already exists')
    command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
               '-f', 'image2pipe', '-framerate', '20', '-vcodec', 'png', '-i', '-',
               '-an', '-c:v', 'ffv1', '-threads', '1', str(output)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for row in packet['rows']:
            frame = row['original_frame']
            path = root / camera / f'{frame:06d}.png'
            if not path.is_file() or sha(path) != row['camera_png_sha256'][camera]:
                raise ValueError('original camera PNG source changed')
            process.stdin.write(path.read_bytes())
        process.stdin.close()
        error = process.stderr.read()
        if process.wait(timeout=300):
            raise ValueError('lossless original camera encode failed: ' + error.decode(errors='replace')[-500:])
    except BaseException:
        process.kill()
        process.wait()
        output.unlink(missing_ok=True)
        raise
    finally:
        process.stderr.close()
    return output


def publish(root, *, packet, camera_manifest, site, road_bytes, restoration_verified,
            expected_frames=900, diagnostic=False):
    """Write Core-shaped sources only after original map and four streams agree."""
    root = Path(root).resolve(strict=True)
    if restoration_verified is not True:
        raise ValueError('Native world restoration must be verified before publication')
    if packet.get('diagnostic') is not diagnostic or packet.get('rows_sha256') != _sha(packet.get('rows')):
        raise ValueError('Native original packet provenance or row seal differs')
    if packet.get('frame_count') != expected_frames or len(packet['rows']) != expected_frames:
        raise ValueError('full original 20 Hz capture absent')
    if not isinstance(road_bytes, bytes) or not road_bytes:
        raise ValueError('original OpenDRIVE bytes required')
    if hashlib.sha256(road_bytes).hexdigest() != site.get('map_sha256'):
        raise ValueError('loaded OpenDRIVE differs from surveyed site hash')
    audit_camera_sources(packet, camera_manifest, root, allow_diagnostic=diagnostic)
    if not diagnostic and not camera_manifest.get('sources'):
        raise ValueError('original camera source manifest empty')
    road = root / 'road.xodr'
    if road.exists():
        raise ValueError('original OpenDRIVE already published')
    road.write_bytes(road_bytes)
    from worker_exchange.native_output import FrameMap, seal_capture
    from traffic_spec_adapter.adapter import write_adapter_graph
    import networkx as nx
    trace, evidence, native = [], [], []
    start_time = packet['rows'][0]['elapsed_seconds']
    with FrameMap(root / 'video_frames.jsonl') as mapping:
        for i, row in enumerate(packet['rows']):
            frame = row['original_frame']
            time = row['elapsed_seconds']
            if i and (frame != packet['rows'][i-1]['original_frame'] + 1 or
                      abs(time - start_time - i / 20) > .002):
                raise ValueError('original frame/time history differs')
            mapping.append(frame, time)
            state = row.get('actor_state')
            if not isinstance(state, dict):
                if not diagnostic:
                    raise ValueError('full original walker body readback absent')
                state = {'actor_id': row['walker_id'], 'blueprint': 'walker.pedestrian.diagnostic',
                         'body_vertices_m': [[row['walker_center_xy'][0] + dx,
                                              row['walker_center_xy'][1] + dy, 0.0]
                                             for dx, dy in ((-.2,-.2),(.2,-.2),(-.2,.2),(.2,.2))],
                         'velocity_mps': [0.0,0.0,0.0], 'heading_deg': 0.0}
            vertices = state['body_vertices_m']
            if (state['actor_id'] != row['walker_id'] or len(vertices) < 4 or
                    any(len(v) != 3 or not all(math.isfinite(float(x)) for x in v) for v in vertices)):
                raise ValueError('original walker body source invalid')
            z = min(vertex[2] for vertex in vertices)
            pos = [*row['walker_center_xy'], z]
            velocity = state['velocity_mps']
            speed = math.sqrt(sum(v*v for v in velocity))
            observation = {'frame': frame, 'time_s': time,
                           'participants': [state],
                           'devices': row['devices'],
                           'map_context': {'source_map_sha256': site['map_sha256'],
                                           'intersection_polygon': site['intersection_polygon']}}
            graph = nx.DiGraph()
            graph.graph.update(frame=frame, time_s=time, observed_evidence=observation)
            graph_name = f'graphs/base/{frame:08d}.adapter.json'
            graph_path = root / 'capture/native' / graph_name
            graph_path.parent.mkdir(parents=True, exist_ok=True)
            write_adapter_graph(graph, graph_path)
            native.append({'frame': frame, 'simulation_time': time, 'adapter_graph': graph_name})
            trace.append({'frame': frame, 'time_s': time,
                          'position_m': pos, 'position': dict(zip(('x','y','z'), pos)),
                          'velocity_mps': velocity, 'heading_deg': state['heading_deg'],
                          'speed_mps': speed, 'speed_mph': speed / .44704, 'control': {}})
            evidence.append({'actor_id': row['walker_id'], 'original_frame': frame,
                             'replay_frame': frame, 'recording_time_s': time,
                             'replay_simulation_time_s': time,
                             'ego': {'body_vertices_m': vertices, 'position_m': pos,
                                     'heading_deg': state['heading_deg'], 'speed_mps': speed,
                                     'speed_provenance': 'synthetic_native_sample' if diagnostic else 'original_trace_actor_get_velocity'},
                             'original_observations': observation,
                             'world': {'weather': {}}})
    lines(root / 'trace.jsonl', trace)
    lines(root / 'capture/evidence.jsonl', evidence)
    lines(root / 'capture/native/frames.jsonl', native)
    original_actor = packet['rows'][0].get('actor_state') or {}
    blueprint = original_actor.get('blueprint', 'walker.pedestrian.0001' if diagnostic else None)
    if not isinstance(blueprint, str) or not blueprint.startswith('walker.pedestrian.'):
        raise ValueError('original pedestrian blueprint source missing')
    (root / 'capture/recorder_info.txt').write_text(
        f'Create {packet["walker_id"]}: {blueprint} at surveyed crossing\n', encoding='utf-8')
    write(root / 'capture/manifest.json', {
        'acquisition': 'synthetic_fixture' if diagnostic else 'original_live_run',
        'diagnostic_fixture': diagnostic, 'case_id': packet['case_id'],
        'extraction_confirmed': True, 'frames': expected_frames,
        'sources': {'road.xodr': sha(road), 'trace.jsonl': sha(root/'trace.jsonl')}})
    for camera in CAMERAS:
        encode_camera(root, packet, camera, diagnostic=diagnostic)
    write(root / 'acquisition-provenance.json', {
        'provenance_kind': 'synthetic_fixture' if diagnostic else 'native',
        'diagnostic_fixture': diagnostic, 'physical_acceptance_claimed': False})
    receipt = seal_capture(root, frames=expected_frames,
                           restoration={'restored': True}, errors=[],
                           encoder_exit_codes={camera: 0 for camera in CAMERAS},
                           context={'map_sha256': sha(road),
                                    'site_sha256': packet['site_sha256'],
                                    'physical_acceptance_claimed': False})
    return receipt
