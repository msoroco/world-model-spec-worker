"""Publish source-sealed original flagger ticks and four cameras as Native output."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import subprocess

from capture_seal import CAMERAS, seal
from flagger_zone import SOURCES


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, sort_keys=True, separators=(',', ':'), allow_nan=False)
        stream.write('\n')


def jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n')


def encode(root, source, frames, view):
    target = root / (view + '.mkv')
    if target.exists():
        raise ValueError('original flagger video output exists')
    command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
               '-f', 'image2pipe', '-framerate', '20', '-vcodec', 'png', '-i', '-',
               '-an', '-c:v', 'ffv1', '-threads', '1', str(target)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for item in frames:
            frame = source / item['path']
            if frame.is_symlink() or not frame.is_file() or sha(frame) != item['sha256']:
                raise ValueError('original synchronized flagger RGB frame missing')
            process.stdin.write(frame.read_bytes())
        process.stdin.close()
        error = process.stderr.read()
        if process.wait(timeout=300) != 0:
            raise ValueError('original flagger RGB encode failed: ' + error.decode(errors='replace')[-300:])
    except Exception:
        process.kill()
        process.wait()
        raise
    finally:
        process.stderr.close()


def publish(root, *, source_dir, map_bytes, restored):
    root, source = Path(root), Path(source_dir)
    if restored is not True or type(map_bytes) is not bytes or not map_bytes:
        raise ValueError('original map and restored Native owner required')
    source_seal = seal(source)
    if source_seal['source_frame_count'] != 900 or source_seal['source_kind'] != 'original_reviewed':
        raise ValueError('source-sealed original flagger capture incomplete')
    packet = json.loads((source / 'source-packet.json').read_text())
    if hashlib.sha256(map_bytes).hexdigest() != packet['scene']['map_opendrive_sha256']:
        raise ValueError('loaded original OpenDRIVE differs from reviewed map')
    rows = [json.loads(line) for line in (source / 'original-ticks.jsonl').read_text().splitlines()]
    cameras = json.loads((source / 'camera-source-manifest.json').read_text())['cameras']
    from traffic_spec_adapter.adapter import write_adapter_graph
    from worker_exchange.native_output import seal_capture
    import networkx as nx
    road = root / 'road.xodr'
    if road.exists():
        raise ValueError('original road output exists')
    road.write_bytes(map_bytes)
    trace, mapping, evidence, native = [], [], [], []
    for index, row in enumerate(rows):
        frame, time_s = row['original_frame'], row['time_s']
        for key in ('vehicle_actor_id', 'vehicle_blueprint', 'vehicle_z',
                    'vehicle_heading_x', 'vehicle_heading_y', 'vehicle_body_vertices_m'):
            if key not in row:
                raise ValueError('original Native vehicle geometry missing: ' + key)
        blueprint = row['vehicle_blueprint']
        if not isinstance(blueprint, str) or not blueprint.startswith('vehicle.'):
            raise ValueError('original motor vehicle blueprint missing')
        heading = math.degrees(math.atan2(row['vehicle_heading_y'], row['vehicle_heading_x']))
        x, y = row['vehicle_xy']
        z = row['vehicle_z']
        speed = row['vehicle_speed_mps']
        position = [x, y, z]
        velocity = [speed * row['vehicle_heading_x'], speed * row['vehicle_heading_y'], 0.0]
        participant = {'actor_id': int(row['vehicle_actor_id']), 'blueprint': blueprint,
                       'blueprint_attributes': {'base_type': 'car'},
                       'position_m': position, 'body_vertices_m': row['vehicle_body_vertices_m'],
                       'heading_deg': heading, 'velocity_mps': velocity, 'speed_mps': speed}
        observation = {'frame': frame, 'time_s': time_s, 'participants': [participant],
                       'world_settings': {'no_rendering_mode': False},
                       'rgb_sensors': [{'view': view, 'source': 'original_native_callback_rgb'} for view in CAMERAS],
                       'flagger_observation': {'driver_id': row['driver_id'],
                           'flagger_id': row['flagger_id'], 'designated': row['designated'],
                           'marked_construction': row['marked_construction'],
                           'authorized': row['authorized'], 'signal': row['signal'],
                           'signal_visible': row['signal_visible'],
                           'intended_vehicle_id': row['intended_vehicle_id'],
                           'source_sha256': {name: row[name + '_source_sha256'] for name in SOURCES},
                           'map_sha256': packet['scene']['map_opendrive_sha256']}}
        graph = nx.DiGraph()
        graph.graph.update(frame=frame, time_s=time_s, observed_evidence=observation)
        graph_name = f'graphs/base/{frame:08d}.adapter.json'
        target = root / 'capture/native' / graph_name
        target.parent.mkdir(parents=True, exist_ok=True)
        write_adapter_graph(graph, target)
        native.append({'frame': frame, 'simulation_time': time_s, 'adapter_graph': graph_name})
        mapping.append({'video_frame': index, 'carla_frame': frame, 'native_frame': frame, 'time_s': time_s})
        trace.append({'frame': frame, 'time_s': time_s,
                      'position': {'x': x, 'y': y, 'z': z}, 'position_m': position,
                      'velocity_mps': velocity, 'heading_deg': heading,
                      'speed_mps': speed, 'control': {}})
        evidence.append({'actor_id': int(row['vehicle_actor_id']), 'original_frame': frame,
                         'replay_frame': frame, 'recording_time_s': time_s,
                         'replay_simulation_time_s': time_s,
                         'ego': {'body_vertices_m': row['vehicle_body_vertices_m'],
                                 'position_m': position, 'heading_deg': heading,
                                 'speed_mps': speed, 'speed_provenance': 'original_native_actor_readback'},
                         'original_observations': observation, 'world': {'weather': {}}})
    jsonl(root / 'trace.jsonl', trace)
    jsonl(root / 'video_frames.jsonl', mapping)
    jsonl(root / 'capture/evidence.jsonl', evidence)
    jsonl(root / 'capture/native/frames.jsonl', native)
    (root / 'capture/recorder_info.txt').write_text('Original Native flagger-zone capture\n')
    write(root / 'capture/manifest.json', {'acquisition': 'original_live_run',
          'diagnostic_fixture': False, 'extraction_confirmed': True, 'frames': 900,
          'observation_contract_version': 2,
          'sources': {'road.xodr': sha(road), 'trace.jsonl': sha(root / 'trace.jsonl')},
          'scope': 'source-hashed zone, flagger signal, original response and four RGB callbacks'})
    for view in CAMERAS:
        encode(root, source, cameras[view], view)
    write(root / 'acquisition-provenance.json', {'provenance_kind': 'native',
          'diagnostic_fixture': False, 'physical_acceptance_claimed': False})
    return seal_capture(root, frames=900, restoration={'restored': True}, errors=[],
                        encoder_exit_codes={view: 0 for view in CAMERAS},
                        context={'map_sha256': sha(road),
                                 'source_packet_sha256': source_seal['packet_sha256'],
                                 'physical_acceptance_claimed': False})
