"""Project source-verified crossing frames into canonical recording channels."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def description(attempt, case_id):
    attempt = Path(attempt)
    if (attempt/'construction.json').is_file():
        construction = json.loads((attempt/'construction.json').read_text())
        if construction['case_id'] != case_id:
            raise ValueError('exact construction differs from source case')
        return construction['recording_description']
    source = Path(__file__).resolve().parent/'proposals/cases.json'
    rows = [row for row in json.loads(source.read_text())['cases'] if row['case_id']==case_id]
    if len(rows)!=1:
        raise ValueError('exact canonical recording description missing')
    return rows[0]['recording_description']


def project(attempt, case_id):
    """Write derived streams once; original source bytes remain untouched."""
    attempt = Path(attempt).resolve()
    trace = json.loads((attempt/'original-trace.json').read_text())
    index = json.loads((attempt/'original-camera-index.json').read_text())
    survey = json.loads((attempt/'crossing-survey.json').read_text())
    rows = trace['frames']
    if trace['case_id'] != case_id or index['case_id'] != case_id or len(rows)!=900:
        raise ValueError('exact original crossing frames required for evidence')
    cameras = index['channels']
    if set(cameras)!={'front','rear','left','right'} or any(len(value)!=900 for value in cameras.values()):
        raise ValueError('complete original camera index required for evidence')
    planned = description(attempt,case_id)
    channel_values = {
        'ego_body_history': [row['ego'] for row in rows],
        'other_body_history': [row['other'] for row in rows],
        'governing_device_history': [row['governing_device_readback'] for row in rows],
        'original_camera_index': [
            {name:cameras[name][i] for name in ('front','rear','left','right')}
            for i in range(900)],
    }
    expected={row['name'] for row in planned['channels']}
    if expected!=set(channel_values):
        raise ValueError('canonical crossing channel plan differs')
    folder = attempt/'channels'
    folder.mkdir(exist_ok=True)
    evidence=[]
    for channel in planned['channels']:
        name=channel['name']
        path=folder/(name+'.jsonl')
        with path.open('x') as stream:
            for row,value in zip(rows,channel_values[name]):
                stream.write(json.dumps({'time_s':row['time_s'],'value':value},allow_nan=False)+'\n')
        evidence.append({'name':name,'unit':channel['unit'],'reference':str(path.relative_to(attempt))})
    context = {'crossing_geometry':{'crossing_kind':survey['crossing_kind'],
                                    'crossing_bounds_xy_m':survey['crossing_bounds_xy_m'],
                                    'approach_road_ids':survey['approach_road_ids'],
                                    'survey_sha256':hashlib.sha256((attempt/'crossing-survey.json').read_bytes()).hexdigest()},
               'governing_device':{'kind':survey['governing_device'],
                                   'states':sorted({row['governing_device_readback'] for row in rows})}}
    context_path=folder/'context.json'
    context_path.write_text(json.dumps(context,allow_nan=False)+'\n')
    for item in planned['context_inputs']:
        if item['name'] not in context:
            raise ValueError('canonical crossing context missing: '+item['name'])
        evidence.append({'name':item['name'],'unit':item['unit'],
                         'reference':str(context_path.relative_to(attempt))})
    return planned,evidence
