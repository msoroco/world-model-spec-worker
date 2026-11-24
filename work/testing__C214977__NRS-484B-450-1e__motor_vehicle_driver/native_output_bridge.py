"""Project sealed original crosswalk callbacks into pinned Native acquisition files."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from crosswalk import require, sealed_json
from native_capture import CAMERAS, CAMERA_SIZES


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists(), 'original output collision: '+str(path))
    path.write_text(json.dumps(value, separators=(',', ':'), allow_nan=False)+'\n')


def _write_lines(path, values):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists(), 'original output collision: '+str(path))
    with path.open('x') as stream:
        for value in values:
            stream.write(json.dumps(value, separators=(',', ':'), allow_nan=False)+'\n')


def _encode(root, camera, output, frames):
    """Encode exactly the retained PNG bytes in callback order as lossless FFV1."""
    target = root/(output+'.mkv')
    require(not target.exists(), 'original video collision')
    command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
               '-f', 'image2pipe', '-framerate', '20', '-vcodec', 'png', '-i', '-',
               '-frames:v', str(len(frames)), '-an', '-c:v', 'ffv1', '-threads', '1', str(target)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for item in frames:
            path = (root/item['path']).resolve()
            require(path.is_relative_to(root) and path.is_file(), 'camera source escapes attempt')
            raw = path.read_bytes()
            require(hashlib.sha256(raw).hexdigest() == item['sha256'], 'original camera hash differs')
            process.stdin.write(raw)
        process.stdin.close()
        error = process.stderr.read()
        require(process.wait(timeout=600) == 0, 'original video encoding failed: '+error.decode(errors='replace')[-500:])
    except Exception:
        process.kill()
        process.wait()
        raise
    finally:
        process.stderr.close()
    require(target.is_file() and target.stat().st_size > 0, 'original video missing')
    return {'path': target.name, 'sha256': _sha(target), 'frames': len(frames),
            'size': list(CAMERA_SIZES[camera])}


def seal_original_capture(attempt, case, map_text, *, restoration_verified):
    """Seal only after a successful Native world restoration; never infer acceptance."""
    require(restoration_verified is True, 'Native world restoration required')
    root = Path(attempt).resolve()
    receipt_path = root/'native-receipt.json'
    receipt_ref = {'path':'native-receipt.json', 'sha256':_sha(receipt_path)}
    receipt = sealed_json(receipt_ref, root)
    site = sealed_json(receipt['site_source'], root)
    map_sha = hashlib.sha256(map_text.encode()).hexdigest()
    require(site['native_opendrive_sha256'] == map_sha, 'reviewed OpenDRIVE hash differs')
    from saved_crosswalk import verify
    verified = verify(receipt_ref, root, root, case)
    require(verified['decoded_original_pngs'] == 3600, 'original four-camera decode incomplete')
    rows = sealed_json(receipt['sources']['actor_rows'], root)
    mapping = sealed_json(receipt['sources']['frame_map'], root)
    cameras = sealed_json(receipt['sources']['camera_readbacks'], root)
    require(len(rows) == len(mapping) == 900, 'original trace incomplete')
    road = root/'road.xodr'
    require(not road.exists(), 'original road source collision')
    road.write_text(map_text)

    from worker_exchange.native_output import FrameMap, seal_capture
    from traffic_spec_adapter.adapter import write_adapter_graph
    import networkx as nx
    trace, evidence, graph_frames = [], [], []
    with FrameMap(root/'video_frames.jsonl') as frame_map:
        for index, row in enumerate(rows):
            frame, time_s = row['frame'], row['time_s']
            require(mapping[index] == {'frame':frame,'time_s':time_s}, 'Native frame map differs')
            frame_map.append(frame, time_s)
            corners = row['body_corners_xy']
            position = row['position_m']
            source_packet = {'frame':frame, 'time_s':time_s, 'subject_id':row['subject_id'],
                             'body_corners_xy':corners, 'speed_mps':row['speed_mps'],
                             'halt_activity':row['halt_activity'],
                             'crosswalk_id':row['crosswalk_id'], 'marking_status':row['marking_status'],
                             'traffic_conflict':row['traffic_conflict'],
                             'law_direction':row['law_direction'],
                             'police_direction':row['police_direction'],
                             'device_direction':row['device_direction']}
            graph = nx.DiGraph()
            graph.graph.update(frame=frame, time_s=time_s, observed_evidence=source_packet)
            graph_name = f'graphs/base/{frame:08d}.adapter.json'
            graph_path = root/'capture/native'/graph_name
            graph_path.parent.mkdir(parents=True, exist_ok=True)
            write_adapter_graph(graph, graph_path)
            graph_frames.append({'frame':frame,'simulation_time':time_s,'adapter_graph':graph_name})
            trace.append({'frame':frame,'time_s':time_s,
                          'position':dict(zip(('x','y','z'),position)),
                          'position_m':position,'velocity_mps':row['velocity_mps'],
                          'heading_deg':row['heading_deg'],
                          'speed_mps':row['speed_mps'], 'speed_mph':row['speed_mps']/0.44704,
                          'control':{}, 'subject_id':row['subject_id']})
            evidence.append({'actor_id':int(row['subject_id']), 'original_frame':frame,
                             'replay_frame':frame,'recording_time_s':time_s,
                             'replay_simulation_time_s':time_s,
                             'ego':{'body_vertices_m':row['body_vertices_m'],
                                    'position_m':position,'heading_deg':row['heading_deg'],
                                    'speed_mps':row['speed_mps'],
                                    'speed_provenance':'original_native_actor_get_velocity'},
                             'original_observations':source_packet,'world':{'weather':{}}})
    _write_lines(root/'trace.jsonl',trace)
    _write_lines(root/'capture/evidence.jsonl',evidence)
    _write_lines(root/'capture/native/frames.jsonl',graph_frames)
    _write(root/'capture/manifest.json',{
        'acquisition':'original_live_run','case_id':case['case_id'],
        'diagnostic_fixture':False,'extraction_confirmed':True,'frames':900,
        'sources':{'road.xodr':map_sha,'trace.jsonl':_sha(root/'trace.jsonl'),
                   'native-receipt.json':receipt_ref['sha256']},
        'scope':'original measured crosswalk actor and four RGB callbacks'})
    videos = {}
    for camera in CAMERAS:
        videos[camera] = _encode(root,camera,camera,cameras[camera])
    _write(root/'acquisition-provenance.json',{
        'provenance_kind':'native','diagnostic_fixture':False,
        'source_format':'original_live_run','physical_acceptance_claimed':False})
    seal_capture(root,frames=900,restoration={'restored':True},errors=[],
                 encoder_exit_codes={name:0 for name in CAMERAS},
                 context={'site_sha256':receipt['site_source']['sha256'],
                          'map_sha256':map_sha,'physical_acceptance_claimed':False})
    return root/'capture-seal.json'
