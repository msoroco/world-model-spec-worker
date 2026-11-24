"""Capture original median-crossing actor, clock, device and camera sources.

The injected adapter owns CARLA calls. No imported simulator or diagnostic
fixture can stand in for an absent original readback in this boundary.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from entry_timing import ASSIGNMENT, CASES, measure

CAMERAS = ('front', 'rear', 'left', 'right')


def _check_fresh_destination(output, case_id):
    if not output.exists() or not any(output.iterdir()):
        return
    construction_path = output/'construction.json'
    selection_path = output/'candidate-selection.json'
    if not construction_path.is_file() or not selection_path.is_file():
        raise ValueError('refusing to overwrite original crossing attempt')
    construction = json.loads(construction_path.read_text())
    selection = json.loads(selection_path.read_text())
    if construction.get('case_id') != case_id or selection.get('case_id') != case_id:
        raise ValueError('materialized exact case differs')
    if selection.get('construction_sha256') != hashlib.sha256(construction_path.read_bytes()).hexdigest():
        raise ValueError('materialized construction digest differs')
    allowed = {'construction.json', 'candidate-selection.json'}
    for item in construction.get('files', []):
        relative = item.get('path')
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or '..' in Path(relative).parts:
            raise ValueError('materialized bundle path invalid')
        path = output/relative
        if not path.is_file() or path.read_text() != item.get('content'):
            raise ValueError('materialized bundle file differs')
        allowed.add(relative)
    observed = {str(path.relative_to(output)) for path in output.rglob('*') if path.is_file()}
    if observed != allowed:
        raise ValueError('refusing to overwrite original crossing attempt')


def _source_path(root, relative):
    if not isinstance(relative, str) or not relative:
        raise ValueError('original camera source path missing')
    path = Path(relative)
    if path.is_absolute() or any(part in ('.', '..') for part in path.parts):
        raise ValueError('original camera source escapes attempt')
    target = (root/path).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise ValueError('original camera source missing')
    return target


def capture(adapter, survey_path, survey_sha256, map_source_path, case_id, output):
    """Run one 45 s source-gated original Native attempt.

    Adapter: verify_map, spawn_actors, configure_cameras, request_controls,
    tick, actor_snapshot, signal_readback, camera_frame, emergency_stop,
    destroy. Every saved field comes from post-tick readback.
    """
    if case_id not in {ASSIGNMENT+'__'+suffix for suffix in CASES}:
        raise ValueError('foreign exact timing case')
    output = Path(output)
    _check_fresh_destination(output, case_id)
    raw_survey = Path(survey_path).read_bytes()
    if hashlib.sha256(raw_survey).hexdigest() != survey_sha256:
        raise ValueError('original crossing survey hash differs')
    survey = json.loads(raw_survey)
    raw_map = Path(map_source_path).read_bytes()
    if hashlib.sha256(raw_map).hexdigest() != survey.get('opendrive_sha256'):
        raise ValueError('original OpenDRIVE source hash differs')
    if survey.get('cell_id') != 'C125751' or survey.get('crossing_kind') != 'median_opening_roadway_crossing':
        raise ValueError('original median roadway crossing identity required')
    if survey.get('governing_device') != 'official_traffic_light':
        raise ValueError('original governing traffic light required')
    adapter.verify_map(survey, raw_map)
    handles = {}
    camera_bound = False
    rows = []
    media = {name: [] for name in CAMERAS}
    first_frame = first_time = None
    output.mkdir(parents=True, exist_ok=True)
    try:
        from scenario_pipeline.worker_exchange.native_output import FrameMap
        handles = adapter.spawn_actors(survey, case_id)
        if not isinstance(handles, dict) or set(handles) != {'ego', 'other'}:
            raise ValueError('two original crossing actors required')
        adapter.configure_cameras(handles['ego'], CAMERAS, fps=20, output=output)
        camera_bound = True
        with FrameMap(output/'video_frames.jsonl') as frame_map:
            for index in range(900):
                adapter.request_controls(handles, case_id, index)
                frame, elapsed = adapter.tick()
                if type(frame) is not int or type(elapsed) not in (int, float) or not math.isfinite(elapsed):
                    raise ValueError('original Native frame/clock missing')
                if first_frame is None:
                    first_frame, first_time = frame, elapsed
                if frame != first_frame+index or not math.isclose(elapsed-first_time,index/20,abs_tol=.002):
                    raise ValueError('original Native frame/clock discontinuity')
                actors = {name: adapter.actor_snapshot(handle, frame) for name,handle in handles.items()}
                row = {'frame': index, 'time_s': index/20,
                       'native_frame_id': frame, 'native_elapsed_seconds': elapsed,
                       'governing_device_readback': adapter.signal_readback(survey, frame),
                       **actors}
                rows.append(row)
                for name in CAMERAS:
                    ref = adapter.camera_frame(name, frame)
                    if not isinstance(ref, dict) or ref.get('frame') != frame or ref.get('channel') != name:
                        raise ValueError('original camera frame join differs')
                    path = _source_path(output, ref.get('source_path'))
                    if hashlib.sha256(path.read_bytes()).hexdigest() != ref.get('source_sha256'):
                        raise ValueError('original camera source hash differs')
                    media[name].append(ref)
                frame_map.append(frame,elapsed)
        actor_ids = {name: handles[name].id for name in handles}
        trace = {'case_id': case_id, 'map_sha256': survey['opendrive_sha256'],
                 'actor_ids': actor_ids, 'frames': rows}
        observation = measure(trace, survey)
        trace_path = output/'original-trace.json'
        trace_path.write_text(json.dumps(trace,indent=2)+'\n')
        index_path = output/'original-camera-index.json'
        index_path.write_text(json.dumps({'case_id':case_id,'channels':media},indent=2)+'\n')
        (output/'crossing-survey.json').write_bytes(raw_survey)
        (output/'original-map.xodr').write_bytes(raw_map)
        manifest = {'case_id':case_id,'source_kind':'original_native_acquisition',
                    'survey_sha256':survey_sha256,
                    'survey':{'path':'crossing-survey.json','sha256':survey_sha256},
                    'opendrive':{'path':'original-map.xodr','sha256':survey['opendrive_sha256']},
                    'trace':{'path':trace_path.name,'sha256':hashlib.sha256(trace_path.read_bytes()).hexdigest()},
                    'camera_index':{'path':index_path.name,'sha256':hashlib.sha256(index_path.read_bytes()).hexdigest()},
                    'frame_map':{'path':'video_frames.jsonl','sha256':hashlib.sha256((output/'video_frames.jsonl').read_bytes()).hexdigest()}}
        (output/'source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        return {'source_manifest':manifest,'observation':observation,
                'physical_acceptance_claimed':False}
    finally:
        try:
            if camera_bound:
                adapter.close_cameras()
        finally:
            for name in ('other','ego'):
                if name in handles:
                    try:
                        adapter.emergency_stop(handles[name])
                    finally:
                        adapter.destroy(handles[name])
