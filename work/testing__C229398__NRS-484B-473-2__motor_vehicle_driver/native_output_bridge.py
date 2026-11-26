"""Publish sealed original parked-light observations in the Native output format.

Only verified original ticks and camera bytes enter this bridge. It never
derives lamp state from a requested configuration or creates original sources.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import subprocess

from capture_seal import CAMERAS, seal
from parked_lamps import valid_number
from source_packet import sha


def require(ok, message):
    if not ok:
        raise ValueError(message)


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(data, stream, sort_keys=True, separators=(',', ':'), allow_nan=False)
        stream.write('\n')


def write_jsonl(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        for row in data:
            stream.write(json.dumps(row, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False) + '\n')


def encode(stage, frames, name):
    output = stage / (name + '.mkv')
    require(not output.exists(), 'original video output exists')
    process = subprocess.Popen(
        ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
         '-f', 'image2pipe', '-framerate', '20', '-vcodec', 'png',
         '-i', '-', '-an', '-c:v', 'ffv1', '-threads', '1', str(output)],
        stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for row in frames:
            process.stdin.write((stage / row['path']).read_bytes())
        process.stdin.close()
        error = process.stderr.read()
        require(process.wait(timeout=300) == 0,
                'original RGB encode failed: ' + error.decode(errors='replace')[-300:])
    except Exception:
        process.kill()
        process.wait()
        raise
    finally:
        process.stderr.close()


def participant(row):
    actor = row.get('actor_id')
    blueprint = row.get('vehicle_blueprint')
    point = row.get('position_m')
    heading = row.get('heading_deg')
    body = row.get('body_vertices_m')
    require(type(actor) is int and actor >= 0 and isinstance(blueprint, str)
            and blueprint.startswith('vehicle.'), 'original vehicle actor readback absent')
    require(isinstance(point, list) and len(point) == 3 and
            all(valid_number(v) for v in point) and valid_number(heading),
            'original vehicle pose readback absent')
    require(isinstance(body, list) and len(body) >= 4 and
            all(isinstance(p, list) and len(p) >= 2 and
                all(valid_number(v) for v in p[:2]) for p in body),
            'original vehicle body readback absent')
    speed = row['speed_mps']
    velocity = [speed * math.cos(math.radians(heading)),
                speed * math.sin(math.radians(heading)), 0.0]
    return {'actor_id': actor, 'blueprint': blueprint,
            'blueprint_attributes': {'base_type': 'car'},
            'position_m': point, 'body_vertices_m': body,
            'heading_deg': heading, 'velocity_mps': velocity,
            'speed_mps': speed}


def publish(stage, *, restored):
    """Require owner restoration and original packet, then write Native outputs."""
    stage = Path(stage)
    require(restored is True, 'original Native world restoration required')
    receipt = seal(stage)
    packet = json.loads((stage / 'source-packet.json').read_text())
    rows = [json.loads(line) for line in
            (stage / 'original-ticks.jsonl').read_text().splitlines()]
    require(len(rows) == 900 and receipt['source_kind'] == 'original_reviewed',
            'original source-bound 900-frame capture required')
    map_file = stage / packet['source_refs']['map_opendrive']['path']
    require(sha(map_file) == packet['scene']['map_opendrive_sha256'],
            'reviewed loaded OpenDRIVE hash differs')
    road = stage / 'road.xodr'
    require(not road.exists(), 'original road output exists')
    road.write_bytes(map_file.read_bytes())
    from traffic_spec_adapter.adapter import write_adapter_graph
    from worker_exchange.native_output import seal_capture
    import networkx as nx
    trace, mapping, evidence, native = [], [], [], []
    for index, row in enumerate(rows):
        frame, time_s = row['original_frame'], row['time_s']
        vehicle = participant(row)
        observation = {'frame': frame, 'time_s': time_s,
                       'participants': [vehicle],
                       'world_settings': {'no_rendering_mode': False},
                       'rgb_sensors': [{'view': view,
                                        'source': 'original_native_callback_rgb'}
                                       for view in CAMERAS],
                       'parked_lamp_observation': {
                           'vehicle_id': row['vehicle_id'],
                           'night': row['night'],
                           'lawful_park': row['lawful_park'],
                           'displayed_lamp_mode': row['lamp_mode'],
                           'auxiliary_lamp': row['auxiliary_lamp'],
                           'beam_aim_deg': row['beam_aim_deg'],
                           'speed_mps': row['speed_mps'],
                           'map_sha256': sha(road)}}
        graph = nx.DiGraph()
        graph.graph.update(frame=frame, time_s=time_s,
                           observed_evidence=observation)
        graph_name = f'graphs/base/{frame:08d}.adapter.json'
        target = stage / 'capture/native' / graph_name
        target.parent.mkdir(parents=True, exist_ok=True)
        write_adapter_graph(graph, target)
        native.append({'frame': frame, 'simulation_time': time_s,
                       'adapter_graph': graph_name})
        mapping.append({'video_frame': index, 'carla_frame': frame,
                        'native_frame': frame, 'time_s': time_s})
        trace.append({'frame': frame, 'time_s': time_s,
                      'position': dict(zip(('x', 'y', 'z'), vehicle['position_m'])),
                      'position_m': vehicle['position_m'],
                      'velocity_mps': vehicle['velocity_mps'],
                      'heading_deg': vehicle['heading_deg'],
                      'speed_mps': row['speed_mps'], 'control': {}})
        evidence.append({'actor_id': vehicle['actor_id'],
                         'original_frame': frame, 'replay_frame': frame,
                         'recording_time_s': time_s,
                         'replay_simulation_time_s': time_s,
                         'ego': {'body_vertices_m': vehicle['body_vertices_m'],
                                 'position_m': vehicle['position_m'],
                                 'heading_deg': vehicle['heading_deg'],
                                 'speed_mps': row['speed_mps'],
                                 'speed_provenance': 'original_native_actor_readback'},
                         'original_observations': observation,
                         'world': {'weather': {}}})
    write_jsonl(stage / 'trace.jsonl', trace)
    write_jsonl(stage / 'video_frames.jsonl', mapping)
    write_jsonl(stage / 'capture/evidence.jsonl', evidence)
    write_jsonl(stage / 'capture/native/frames.jsonl', native)
    (stage / 'capture/recorder_info.txt').write_text(
        'Original Native parked-light capture\n')
    write_json(stage / 'capture/manifest.json', {
        'acquisition': 'original_live_run', 'diagnostic_fixture': False,
        'extraction_confirmed': True, 'frames': 900,
        'observation_contract_version': 2,
        'sources': {'road.xodr': sha(road),
                    'trace.jsonl': sha(stage / 'trace.jsonl')},
        'scope': 'reviewed parked vehicle, lamp-state telemetry and four RGB callbacks'})
    cameras = json.loads((stage / 'camera-source-manifest.json').read_text())['cameras']
    for view in CAMERAS:
        encode(stage, cameras[view], view)
    write_json(stage / 'acquisition-provenance.json', {
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'physical_acceptance_claimed': False})
    return seal_capture(stage, frames=900, restoration={'restored': True},
                        errors=[], encoder_exit_codes={view: 0 for view in CAMERAS},
                        context={'map_sha256': sha(road),
                                 'source_packet_sha256': receipt['packet_sha256'],
                                 'physical_acceptance_claimed': False})
