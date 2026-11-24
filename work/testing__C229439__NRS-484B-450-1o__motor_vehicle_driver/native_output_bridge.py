"""Seal original CARLA rows and camera callbacks for the pinned saved pipeline.

The graph projection retains the observed packet; it does not infer an official
sign, a legal prohibition, or physical acceptance from the CARLA prop class.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from zipfile import ZipFile


CAMERA_OUTPUTS = {'front': 'overview', 'rear': 'approach',
                  'left': 'reference_corner', 'right': 'driver_reference'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    if path.exists():
        raise ValueError('retained original output already exists: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n')


def write_jsonl(path, rows):
    path = Path(path)
    if path.exists():
        raise ValueError('retained original output already exists: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        for row in rows:
            stream.write(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n')


def encode_archive(archive, video, members, *, fps=20):
    """Derive FFV1 video from all original source PNGs in capture order."""
    if Path(video).exists() or not members:
        raise ValueError('fresh output and nonempty original frame order required')
    command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
               '-f', 'image2pipe', '-framerate', str(fps), '-vcodec', 'png', '-i', '-',
               '-an', '-c:v', 'ffv1', '-threads', '1', str(video)]
    with ZipFile(archive) as source:
        if len(set(members)) != len(members) or source.namelist() != members:
            raise ValueError('original camera archive member order differs')
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for name in members:
                process.stdin.write(source.read(name))
            process.stdin.close()
            error = process.stderr.read()
            if process.wait(timeout=300) != 0:
                raise ValueError('four-view source encoding failed: ' + error.decode(errors='replace')[-500:])
            process.stderr.close()
        except Exception:
            process.kill()
            process.wait()
            process.stderr.close()
            raise
    return {'path': Path(video).name, 'sha256': sha(video), 'frames': len(members), 'fps': fps}


def seal(output, world, *, restoration_verified, expected_dimensions=None):
    """Build original-source projection after actual CARLA world restoration."""
    if restoration_verified is not True:
        raise ValueError('Native world restoration required before capture seal')
    root = Path(output)
    config = json.loads((root / 'config.json').read_text())
    attempt = json.loads((root / 'attempt.json').read_text())
    rows = json.loads((root / 'actor_rows.json').read_text())
    if attempt['source_format'] != 'native_original' or len(rows) != 900:
        raise ValueError('incomplete original 900-tick source')
    if attempt['case_id'] != config['case']['case_id']:
        raise ValueError('original case differs from materialized construction')
    from parking import audit_saved_attempt
    from saved_media_audit import audit_media
    audit_saved_attempt(attempt, root)
    audit_media(attempt, root, expected_dimensions)
    map_text = world.get_map().to_opendrive()
    map_sha = hashlib.sha256(map_text.encode()).hexdigest()
    site = json.loads((root / 'site-source.json').read_text())
    if site.get('native_opendrive_sha256') != map_sha:
        raise ValueError('reviewed site does not bind original Native OpenDRIVE')
    (root / 'road.xodr').write_text(map_text)
    frame_map = []
    trace = []
    evidence = []
    native_frames = []
    from traffic_spec_adapter.adapter import write_adapter_graph
    import networkx as nx
    for index, row in enumerate(rows):
        frame, time_s = row['frame'], row['time_s']
        if frame != attempt['first_frame'] + index or (index and abs(time_s - rows[index - 1]['time_s'] - 0.05) > 0.001):
            raise ValueError('original frame/timestamp gap')
        source_packet = {'frame': frame, 'time_s': time_s, 'participants': [],
                         'map_context': {'source_map_sha256': map_sha},
                         'official_device_observation': {'device_id': row['device_id'],
                             'exact_instruction': row['device_instruction'],
                             'effective': row['device_effective']}}
        graph = nx.DiGraph()
        graph.graph.update(frame=frame, time_s=time_s, observed_evidence=source_packet)
        graph_name = f'graphs/base/{frame:08d}.adapter.json'
        graph_path = root / 'capture/native' / graph_name
        graph_path.parent.mkdir(parents=True, exist_ok=True)
        write_adapter_graph(graph, graph_path)
        native_frames.append({'frame': frame, 'simulation_time': time_s,
                              'adapter_graph': graph_name})
        frame_map.append({'video_frame': index, 'carla_frame': frame,
                          'native_frame': frame, 'time_s': time_s})
        position = row['position_m']
        trace.append({'frame': frame, 'time_s': time_s, 'position': dict(zip(('x', 'y', 'z'), position)),
                      'position_m': position, 'velocity_mps': row['velocity_mps'],
                      'heading_deg': row['heading_deg'], 'speed_mps': row['speed_mps'],
                      'speed_mph': row['speed_mps'] / 0.44704, 'control': {}})
        evidence.append({'actor_id': int(row['subject_id']), 'original_frame': frame,
                         'replay_frame': frame, 'recording_time_s': time_s,
                         'replay_simulation_time_s': time_s,
                         'ego': {'body_vertices_m': row['body_vertices_m'], 'position_m': position,
                                 'heading_deg': row['heading_deg'], 'speed_mps': row['speed_mps'],
                                 'speed_provenance': 'original_trace_actor_get_velocity'},
                         'original_observations': source_packet, 'world': {'weather': {}}})
    write_jsonl(root / 'video_frames.jsonl', frame_map)
    write_jsonl(root / 'trace.jsonl', trace)
    write_jsonl(root / 'capture/evidence.jsonl', evidence)
    write_jsonl(root / 'capture/native/frames.jsonl', native_frames)
    (root / 'capture/recorder_info.txt').write_text(
        f"Create {rows[0]['subject_id']}: {json.loads((root / 'vehicle-source.json').read_text())['blueprint']} (original live) at (0, 0, 0)\n")
    write_json(root / 'capture/manifest.json', {
        'acquisition': 'original_live_run', 'diagnostic_fixture': False,
        'extraction_confirmed': True, 'frames': 900,
        'sources': {'road.xodr': sha(root / 'road.xodr'), 'trace.jsonl': sha(root / 'trace.jsonl')},
        'scope': 'original measured actor, context observer and four RGB callbacks'})
    videos = {}
    for camera, target in CAMERA_OUTPUTS.items():
        members = [row['camera_frames'][camera]['member'] for row in rows]
        videos[target] = encode_archive(root / (camera + '.png.zip'), root / (target + '.mkv'), members)
    write_json(root / 'acquisition-provenance.json', {
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'source_format': 'original_live_run', 'physical_acceptance_claimed': False})
    from worker_exchange.native_output import seal_capture
    seal_capture(root, frames=900, restoration={'restored': True}, errors=[],
                 encoder_exit_codes={name: 0 for name in videos},
                 context={'site_sha256': sha(root / 'site-source.json'),
                          'device_sha256': sha(root / 'device-source.json'),
                          'map_sha256': map_sha,
                          'physical_acceptance_claimed': False})
    return root / 'capture-seal.json'
