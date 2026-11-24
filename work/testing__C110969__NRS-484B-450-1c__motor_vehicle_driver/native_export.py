"""Losslessly export sealed Native PNG callbacks and actor trace for saved processing."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

from PIL import Image

from intersection_observables import _require
from native_media import CAMERAS, audit_saved_acquisition


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n'


def export(attempt, expected_case, *, expected_count=900):
    attempt = Path(attempt).resolve()
    _require(not any((attempt/name).exists() for name in
                     ('video_frames.jsonl', *(name+'.mkv' for name in CAMERAS))),
             'prior Native export exists')
    media = audit_saved_acquisition(attempt)
    _require(media['case_id'] == expected_case and media['frame_count'] == expected_count,
             'exact full Native case/media interval missing')
    original = json.loads((attempt/'trace.json').read_text())
    manifest = json.loads((attempt/'media-manifest.json').read_text())
    samples = original['samples']
    rows = manifest['frame_map']
    _require([x['frame'] for x in samples] == [x['frame'] for x in rows] and
             all(abs(x['time_s']-y['time_s']) <= 1e-6 for x,y in zip(samples, rows)),
             'original actor and camera timestamps differ')
    traces = []
    frame_map = []
    for i, row in enumerate(samples):
        position = row['position_m']
        traces.append({'frame': row['frame'], 'time_s': row['time_s'],
                       'position_m': position,
                       'position': dict(zip(('x','y','z'), position)),
                       'heading_deg': row['heading_deg'], 'speed_mps': row['speed_mps'],
                       'velocity_mps': row['velocity_mps'],
                       'body_footprint': row['body_footprint']})
        frame_map.append({'video_frame': i, 'carla_frame': row['frame'],
                          'native_frame': row['frame'], 'time_s': row['time_s']})
    scratch_root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    _require('.runtime-work' in scratch_root.parts,
             'Native export scratch must be under .runtime-work')
    scratch_root.mkdir(parents=True, exist_ok=True)
    from worker_exchange.media import audit as audit_video
    video_receipts = {}
    with tempfile.TemporaryDirectory(dir=scratch_root, prefix='native-export-') as temporary:
        temporary = Path(temporary)
        for camera, dimensions in CAMERAS.items():
            frames = temporary/camera
            frames.mkdir()
            rgb = hashlib.sha256()
            with zipfile.ZipFile(attempt/(camera+'.zip')) as archive:
                for index, row in enumerate(rows):
                    member = row['sources'][camera]['member']
                    raw = archive.read(member)
                    _require(hashlib.sha256(raw).hexdigest() == row['sources'][camera]['sha256'],
                             'original camera PNG seal differs: '+camera)
                    with Image.open(io.BytesIO(raw)) as image:
                        _require(image.size == dimensions and image.format == 'PNG',
                                 'original camera dimensions differ: '+camera)
                        rgb.update(image.convert('RGB').tobytes())
                    (frames/f'{index:08d}.png').write_bytes(raw)
            target = attempt/(camera+'.mkv')
            command = ['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
                       '-framerate','20','-i',str(frames/'%08d.png'),
                       '-c:v','ffv1','-level','3','-pix_fmt','bgr0',str(target)]
            subprocess.run(command, check=True, timeout=600,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            decoded = audit_video(target, len(rows))
            _require(decoded['rgb_sequence_sha256'] == rgb.hexdigest(),
                     'lossless Native camera export changed pixels: '+camera)
            video_receipts[camera] = {'sha256': sha(target),
                                      'decoded_frames': decoded['frames'],
                                      'rgb_sequence_sha256': decoded['rgb_sequence_sha256']}
    trace_path = attempt/'trace.jsonl'
    graph_manifest_path = attempt/'capture'/'manifest.json'
    if graph_manifest_path.is_file():
        graph_manifest = json.loads(graph_manifest_path.read_text())
        _require(graph_manifest.get('extraction_confirmed') is True and
                 graph_manifest.get('frames') == len(traces) and
                 graph_manifest.get('sources', {}).get('trace.jsonl') == sha(trace_path),
                 'original graph capture incomplete or trace seal differs')
        graph_rows = [json.loads(line) for line in trace_path.read_text().splitlines()]
        _require(len(graph_rows) == len(traces), 'original graph trace count differs')
        for graph_row, actor_row in zip(graph_rows, traces):
            _require(graph_row['frame'] == actor_row['frame'] and
                     abs(graph_row['time_s']-actor_row['time_s']) <= 1e-6 and
                     all(abs(x-y) <= 1e-3 for x,y in zip(
                         graph_row['position_m'], actor_row['position_m'])) and
                     abs(graph_row['speed_mps']-actor_row['speed_mps']) <= 1e-3,
                     'original graph/actor telemetry differs')
    else:
        _require(not trace_path.exists(), 'unsealed original trace exists')
        trace_path.write_text(''.join(encoded(row) for row in traces))
    (attempt/'video_frames.jsonl').write_text(''.join(encoded(row) for row in frame_map))
    receipt = {'format':'intersection-native-export-v1', 'case_id':expected_case,
               'original_source_manifest_sha256':sha(attempt/'source-manifest.json'),
               'trace_sha256':sha(attempt/'trace.jsonl'),
               'graph_manifest_sha256':sha(graph_manifest_path) if graph_manifest_path.is_file() else None,
               'frame_map_sha256':sha(attempt/'video_frames.jsonl'),
               'frame_count':len(rows), 'videos':video_receipts,
               'physical_visibility_reviewed':False, 'legal_conclusion':None}
    (attempt/'native-export-receipt.json').write_text(encoded(receipt))
    return receipt
