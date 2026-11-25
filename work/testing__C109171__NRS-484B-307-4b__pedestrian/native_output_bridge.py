"""Publish sealed pedestrian sources to the current Native/Core capture layout."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
DIMENSIONS = {'overview': (1920, 1080), 'approach': (1280, 720),
              'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    if path.exists():
        raise ValueError('original Native publication already exists: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(',', ':'),
                               allow_nan=False) + '\n')


def lines(path, rows):
    path = Path(path)
    if path.exists():
        raise ValueError('original Native publication already exists: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False) + '\n')


def encode(root, frame_map, camera, production):
    from PIL import Image
    import io
    output = root / (camera + '.mkv')
    if output.exists():
        raise ValueError('original camera video already exists')
    command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
               '-f', 'image2pipe', '-framerate', '20', '-vcodec', 'png', '-i', '-',
               '-an', '-c:v', 'ffv1', '-threads', '1', str(output)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for row in frame_map:
            ref = row['cameras'][camera]
            path = root / ref['path']
            raw = path.read_bytes()
            if sha(path) != ref['sha256']:
                raise ValueError('original camera PNG changed: ' + camera)
            with Image.open(io.BytesIO(raw)) as image:
                image.load()
                if production and image.size != DIMENSIONS[camera]:
                    raise ValueError('original camera dimensions differ: ' + camera)
            process.stdin.write(raw)
        process.stdin.close()
        error = process.stderr.read()
        if process.wait(timeout=300):
            raise ValueError('original FFV1 encoding failed: ' + error.decode(errors='replace')[-500:])
    except Exception:
        process.kill()
        process.wait()
        raise
    finally:
        process.stderr.close()


def publish(root, *, map_bytes, restoration_verified, expected_frames=900,
            diagnostic_fixture=False):
    """Seal original 20 Hz walker/official-device frames after world restore."""
    if restoration_verified is not True or type(map_bytes) is not bytes or not map_bytes:
        raise ValueError('original map and world restoration required')
    root = Path(root)
    source = json.loads((root / 'pedestrian-source.json').read_text())
    site = json.loads((root / source['site_ref']['path']).read_text())
    road = root / site['road_xodr_source_path']
    if road.read_bytes() != map_bytes:
        raise ValueError('loaded OpenDRIVE differs from original site source')
    events_path = root / source['events_ref']['path']
    frames_path = root / source['frame_map_ref']['path']
    if sha(events_path) != source['events_ref']['sha256'] or sha(frames_path) != source['frame_map_ref']['sha256']:
        raise ValueError('original event or camera map source changed')
    events = json.loads(events_path.read_text())
    cameras = json.loads(frames_path.read_text())
    if len(events) != len(cameras) or len(events) != expected_frames or expected_frames < 2:
        raise ValueError('incomplete original pedestrian capture')
    road_target = root / 'road.xodr'
    if road_target.exists():
        raise ValueError('original OpenDRIVE has already been published')
    road_target.write_bytes(map_bytes)
    from traffic_spec_adapter.adapter import write_adapter_graph
    import networkx as nx
    trace, mapping, evidence, native = [], [], [], []
    for index, (row, camera_row) in enumerate(zip(events, cameras)):
        frame = row.get('world_frame')
        time = row.get('sim_time_seconds')
        actor = row.get('native_walker_actor')
        if (type(frame) is not int or (index and frame != events[index - 1]['world_frame'] + 1) or
                type(time) not in (int, float) or
                (index and abs(time - events[index - 1]['sim_time_seconds'] - .05) > 1e-4) or
                camera_row.get('frame') != index or camera_row.get('sim_time_seconds') != time or
                set(camera_row.get('cameras', {})) != set(CAMERAS) or
                not isinstance(actor, dict) or
                not str(actor.get('blueprint', '')).startswith('walker.') or
                not isinstance(actor.get('body_vertices_m'), list) or len(actor['body_vertices_m']) < 4 or
                not isinstance(actor.get('velocity_mps'), list) or len(actor['velocity_mps']) != 3):
            raise ValueError('original walker geometry, clock or camera source missing')
        position = [float(row['pedestrian_xy'][0]), float(row['pedestrian_xy'][1]),
                    min(vertex[2] for vertex in actor['body_vertices_m'])]
        packet = {'frame': frame, 'time_s': time, 'participants': [actor],
                  'official_vehicle_head': {'id': row['vehicle_head_id'],
                                            'lit_aspects': row['vehicle_head_lit_aspects']},
                  'separate_pedestrian_device': {'id': row['pedestrian_device_id'],
                                                 'indication': row['pedestrian_device_indication']},
                  'map_context': {'source_map_sha256': sha(road),
                                  'highway_boundary_xy': site['highway_boundary_xy']}}
        graph = nx.DiGraph()
        graph.graph.update(frame=frame, time_s=time, observed_evidence=packet)
        graph_name = f'graphs/base/{frame:08d}.adapter.json'
        graph_path = root / 'capture/native' / graph_name
        graph_path.parent.mkdir(parents=True, exist_ok=True)
        write_adapter_graph(graph, graph_path)
        native.append({'frame': frame, 'simulation_time': time, 'adapter_graph': graph_name})
        mapping.append({'video_frame': index, 'carla_frame': frame,
                        'native_frame': frame, 'time_s': time})
        speed = actor['speed_mps']
        trace.append({'frame': frame, 'time_s': time,
                      'position': dict(zip(('x', 'y', 'z'), position)),
                      'position_m': position, 'velocity_mps': actor['velocity_mps'],
                      'heading_deg': actor['heading_deg'], 'speed_mps': speed,
                      'speed_mph': speed / .44704, 'control': {}})
        evidence.append({'actor_id': actor['actor_id'], 'original_frame': frame,
                         'replay_frame': frame, 'recording_time_s': time,
                         'replay_simulation_time_s': time,
                         'ego': {'body_vertices_m': actor['body_vertices_m'],
                                 'position_m': position, 'heading_deg': actor['heading_deg'],
                                 'speed_mps': speed,
                                 'speed_provenance': 'original_trace_actor_get_velocity'},
                         'original_observations': packet, 'world': {'weather': {}}})
    lines(root / 'trace.jsonl', trace)
    lines(root / 'video_frames.jsonl', mapping)
    lines(root / 'capture/evidence.jsonl', evidence)
    lines(root / 'capture/native/frames.jsonl', native)
    (root / 'capture/recorder_info.txt').write_text(
        f'Create {events[0]["native_walker_actor"]["actor_id"]}: '
        f'{events[0]["native_walker_actor"]["blueprint"]} at surveyed crossing\n')
    write(root / 'capture/manifest.json', {
        'acquisition': 'synthetic_fixture' if diagnostic_fixture else 'original_live_run',
        'diagnostic_fixture': diagnostic_fixture,
        'case_id': source['case_id'], 'extraction_confirmed': True,
        'frames': len(events), 'sources': {'road.xodr': sha(road_target),
                                           'trace.jsonl': sha(root / 'trace.jsonl')}})
    for camera in CAMERAS:
        encode(root, cameras, camera, expected_frames == 900 and not diagnostic_fixture)
    write(root / 'acquisition-provenance.json', {
        'provenance_kind': 'synthetic_fixture' if diagnostic_fixture else 'native',
        'diagnostic_fixture': diagnostic_fixture,
        'physical_acceptance_claimed': False})
    from worker_exchange.native_output import seal_capture
    seal_capture(root, frames=len(events), restoration={'restored': True}, errors=[],
                 encoder_exit_codes={camera: 0 for camera in CAMERAS},
                 context={'map_sha256': sha(road_target),
                          'site_sha256': source['site_ref']['sha256'],
                          'physical_acceptance_claimed': False})
    return root / 'capture-seal.json'
