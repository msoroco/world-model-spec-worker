"""Publish a complete original pedestrian capture to the pinned Native format.

All pixels, graph refs, trace rows and crossing facts come from one sealed
original attempt. This command never creates missing physical observations.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from zipfile import ZipFile

from native_capture import CAMERAS
from saved_media_audit import audit as audit_original_media


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing original source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def publish_original(output, case_id, *, expected_frames=900, encoder=subprocess.run):
    from worker_exchange.native_output import FrameMap, physical_result, validate_result, write_result
    from worker_exchange.media import audit as audit_video

    root = Path(output).resolve()
    marker_path = root / 'fixture-provenance.json'
    diagnostic = marker_path.is_file()
    if diagnostic:
        marker = json.loads(marker_path.read_text())
        if marker.get('diagnostic_fixture') is not True or not marker.get('scope'):
            raise ValueError('explicit diagnostic fixture provenance required')
    receipt = json.loads((root / 'capture-receipt.json').read_text())
    if (receipt.get('case_id') != case_id or receipt.get('frame_count') != expected_frames or
            not isinstance(receipt.get('reviewed_site_source'), dict)):
        raise ValueError('complete reviewed pedestrian capture required')
    original_media = audit_original_media(root)
    if original_media['decoded_images'] != expected_frames * 4:
        raise ValueError('original pedestrian camera completeness differs')
    pipeline = json.loads((root / 'capture/manifest.json').read_text())
    if (pipeline.get('case_id') != case_id or pipeline.get('frames') != expected_frames or
            pipeline.get('extraction_confirmed') is not True):
        raise ValueError('original pedestrian graph capture incomplete')
    trace = _rows(root / 'trace.jsonl')
    evidence = _rows(root / 'capture/evidence.jsonl')
    graphs = _rows(root / 'capture/native/frames.jsonl')
    frames = json.loads((root / 'original-frames.json').read_text())
    if not all(len(rows) == expected_frames for rows in (trace, evidence, graphs, frames)):
        raise ValueError('original pedestrian trace/graph/frame count differs')
    for index, (crossing, row, event, graph) in enumerate(zip(frames, trace, evidence, graphs)):
        frame = crossing['frame']
        if (row.get('frame') != frame or event.get('original_frame') != frame or
                graph.get('frame') != frame or abs(row.get('time_s', -1) - crossing['elapsed_seconds']) > .001 or
                abs(event.get('recording_time_s', -1) - crossing['elapsed_seconds']) > .001):
            raise ValueError('original pedestrian graph/frame/time join differs')
        if index and frame != frames[index - 1]['frame'] + 1:
            raise ValueError('original pedestrian frame gap')
        graph_ref = graph.get('adapter_graph')
        if not isinstance(graph_ref, str):
            raise ValueError('original pedestrian graph source missing')
        path = (root / 'capture/native' / graph_ref).resolve()
        if not path.is_relative_to((root / 'capture/native').resolve()) or not path.is_file():
            raise ValueError('original pedestrian graph source missing')
        payload = json.loads(path.read_text())
        if (payload.get('format') != 'native-adapter-graph-v1' or
                payload.get('metadata', {}).get('frame') != frame or
                not isinstance(payload.get('nodes'), list) or
                not isinstance(payload.get('edges'), list)):
            raise ValueError('original pedestrian graph structure differs')
    mapping = root / 'video_frames.jsonl'
    if mapping.exists():
        raise ValueError('original pedestrian video map already published')
    with FrameMap(mapping) as frame_map:
        for row in frames:
            frame_map.append(row['frame'], row['elapsed_seconds'])
    image_root = root / 'camera-png'
    image_root.mkdir(exist_ok=False)
    for name in CAMERAS:
        archive = root / receipt['camera_sources'][name]['path']
        with ZipFile(archive) as source:
            for index, row in enumerate(frames):
                member = f"{row['frame']:08d}.png"
                payload = source.read(member)
                if hashlib.sha256(payload).hexdigest() != row['camera_frames'][name]['sha256']:
                    raise ValueError('original pedestrian camera pixel changed')
                (image_root / f'{index:04d}-{name}.png').write_bytes(payload)
        video = root / (name + '.mkv')
        if video.exists():
            raise ValueError('original pedestrian video already exists')
        encoder(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                 '-threads', '4', '-framerate', '20', '-i',
                 str(image_root / ('%04d-' + name + '.png')),
                 '-c:v', 'ffv1', str(video)], check=True)
        audit_video(video, expected_frames, mapping_sha256=_sha(mapping))
    config = json.loads((root / 'config.json').read_text())
    recording = json.loads((root / 'construction.json').read_text())['recording_description']
    if {item['name'] for item in recording['channels']} != {'pedestrian_body_center_xy_m'}:
        raise ValueError('unmapped pedestrian recording channel')
    channels = root / 'channels'
    channels.mkdir(exist_ok=False)
    channel = channels / 'pedestrian_body_center_xy_m.jsonl'
    channel.write_text(''.join(json.dumps({'time_s': row['elapsed_seconds'],
        'value': {'x': row['pedestrian_xy'][0], 'y': row['pedestrian_xy'][1]}},
        allow_nan=False) + '\n' for row in frames))
    context = channels / 'source_provenance.json'
    context.write_text(json.dumps({'source_provenance': {
        'kind': 'original_live_run',
        'site_source_sha256': receipt['reviewed_site_source']['sha256'],
        'crossing_frames_sha256': _sha(root / 'original-frames.json'),
        'graph_manifest_sha256': _sha(root / 'capture/manifest.json')}},
        sort_keys=True) + '\n')
    (root / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'synthetic_fixture' if diagnostic else 'native',
        'diagnostic_fixture': diagnostic,
        'source': 'original walker and graph capture',
        'capture_manifest_sha256': _sha(root / 'capture/manifest.json')},
        sort_keys=True) + '\n')
    result = {
        'case_id': case_id,
        'measured_values': {'original_crossing_frames': expected_frames},
        'target_checks': [{'target': 'source-bound pedestrian crossing capture',
                           'requested': True, 'measured': True,
                           'method': 'same-frame original walker, graph and camera source join',
                           'tolerance': 0, 'matched': True,
                           'physical_cause_confirmed': False,
                           'cause_evidence': {'original-frames.json': _sha(root / 'original-frames.json'),
                                              'capture/manifest.json': _sha(root / 'capture/manifest.json')}}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': 'Original capture published; saved physical and legal review pending',
        'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': mapping.name,
        'recording_description': recording,
        'recording_evidence': [
            {'name': 'pedestrian_body_center_xy_m', 'unit': 'structured',
             'reference': str(channel.relative_to(root))},
            {'name': 'source_provenance', 'unit': 'metadata',
             'reference': str(context.relative_to(root))}],
        'realized_observables': {},
    }
    result = physical_result(root, result)
    validate_result(result)
    write_result(root, result)
    return {'case_id': case_id, 'frames': expected_frames,
            'source_manifest_sha256': _sha(root / 'capture/manifest.json'),
            'result_sha256': _sha(root / 'result.json')}
