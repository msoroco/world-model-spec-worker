"""Saved-only fire-station path and body-footprint measurement."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from fire_station_geometry import classify_path


def _source(root, name):
    path = Path(root)/name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: '+name)
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(attempt, write_channels=True):
    root = Path(attempt)
    paths = {}; hashes = {}
    for name in ('config.json', 'station_context.json', 'participant_state.jsonl',
                 'video_frames.jsonl', 'trace.jsonl'):
        paths[name], hashes[name] = _source(root, name)
    config = json.loads(paths['config.json'].read_text())
    context = json.loads(paths['station_context.json'].read_text())
    case = config.get('selected_case_id', '')
    if (config.get('law_id'), config.get('cell_id'), config.get('actor')) != (
            'LVMC-11-12-060', 'C104538', 'motor_vehicle_driver') or not case.endswith('__'+config.get('case_branch','')):
        raise ValueError('Wrong exact fire-station identity')
    if context.get('source') != config.get('station_survey',{}).get('station_source'):
        raise ValueError('Station source differs from selected construction')
    frames = _rows(paths['video_frames.jsonl'])
    participants = _rows(paths['participant_state.jsonl'])
    trace = _rows(paths['trace.jsonl'])
    if len(frames) < 3 or len(frames) != len(participants) or len(frames) != len(trace):
        raise ValueError('Original station source/frame-map length differs')
    samples = []; ego_id = None; previous = None
    for index, (fm, row, motion) in enumerate(zip(frames, participants, trace)):
        frame, time_s = fm.get('carla_frame'), fm.get('time_s')
        if fm.get('video_frame') != index or type(frame) is not int or not isinstance(time_s,(int,float)) or not math.isfinite(time_s):
            raise ValueError('Invalid original frame identity')
        if previous is not None and (frame <= previous[0] or abs(time_s-previous[1]-.05)>.005):
            raise ValueError('Original station samples are not consecutive 20 Hz')
        previous = (frame,time_s)
        if any(v.get('frame') != frame or v.get('time_s') != time_s for v in (row,motion)):
            raise ValueError('Station source/frame-map join failed')
        ego = row.get('ego')
        if not isinstance(ego,dict) or type(ego.get('actor_id')) is not int:
            raise ValueError('Missing original station subject state')
        if ego_id is None: ego_id = ego['actor_id']
        if ego['actor_id'] != ego_id: raise ValueError('Station subject identity changed')
        xy = ego.get('center_xy'); body = ego.get('body_vertices_xy')
        if not isinstance(xy,list) or len(xy)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in xy):
            raise ValueError('Invalid original station position')
        if not isinstance(body,list) or len(body)<4 or any(not isinstance(v,list) or len(v)!=2 for v in body):
            raise ValueError('Missing original full-body vertices')
        if type(ego.get('heading_rad')) not in (int,float) or not math.isfinite(ego['heading_rad']):
            raise ValueError('Invalid original station heading')
        lane = ego.get('lane_id')
        if not isinstance(lane,list) or len(lane)!=2 or any(type(v) is not int for v in lane):
            raise ValueError('Missing original mapped station lane')
        samples.append({'frame':frame,'time_s':time_s,'x_m':xy[0],'y_m':xy[1],
                        'heading_rad':ego['heading_rad'],'lane_id':lane,
                        'body_vertices_xy':body,'speed_mps':ego.get('speed_mps')})
    measured = classify_path(samples,context)
    measured['sample_count'] = len(samples)
    measured['source_hashes'] = hashes
    measured['station_source'] = context['source']
    if write_channels:
        for name, selector in (
            ('subject_center_xy',lambda r:[r['x_m'],r['y_m']]),
            ('subject_heading_rad',lambda r:r['heading_rad']),
            ('subject_body_vertices_xy',lambda r:r['body_vertices_xy']),
            ('subject_lane_id',lambda r:r['lane_id'])):
            destination = root/(name+'.jsonl')
            if destination.exists(): raise ValueError('Retain prior derived station channel: '+name)
            destination.write_text(''.join(json.dumps({'frame':r['frame'],'time_s':r['time_s'],
                'value':selector(r)},allow_nan=False)+'\n' for r in samples))
    return {'format':'worker-analysis-report','case_id':case,
            'measurements':{'station_reversal':{'method':'analyze',
                'sources':{name:hashes[name] for name in ('station_context.json','participant_state.jsonl','video_frames.jsonl','trace.jsonl')},
                'value':measured}},
            'limitations':['Station identity, actual pixels and turning purpose require independent source review.'],
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def build_result(attempt, report):
    root = Path(attempt)
    config = json.loads((root/'config.json').read_text())
    description = config.get('case',{}).get('recording_description')
    if not isinstance(description,dict) or not isinstance(description.get('channels'),list):
        raise ValueError('Selected station recording description missing')
    evidence = []
    for channel in description['channels']:
        path,digest = _source(root,channel['name']+'.jsonl')
        evidence.append({'name':channel['name'],'unit':channel['unit'],
                         'reference':path.name,'sha256':digest})
    measured = report['measurements']['station_reversal']['value']
    return {'case_id':report['case_id'],'measured_values':{'station_reversal':measured},
        'target_checks':[{'target':'original path reversal and station-region relation',
            'requested':'retained original frame path and body footprint',
            'measured':measured['heading_change_deg'],
            'method':'saved original heading and footprint join',
            'tolerance':None,'matched':measured['reversal_observed'],
            'physical_cause_confirmed':False,
            'cause_evidence':'Synthetic CPU fixture cannot establish real station identity or maneuver'}],
        'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':False,
        'termination_reason':'Saved station measurement complete; physical outcome unverified',
        'physical_failure_flags':{'station_identity_unverified':True,'purpose_unresolved':True},
        'trace_reference':'trace.jsonl',
        'video_references':['overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv'],
        'video_frame_map_reference':'video_frames.jsonl',
        'recording_description':description,'recording_evidence':evidence,
        'realized_observables':{'heading_change_deg':{'value':measured['heading_change_deg'],
            'unit':'deg','method':'original first-to-last heading difference',
            'time_window':'all original frames','statistic':'absolute_wrapped_difference',
            'reference':'subject_heading_rad.jsonl'}},
        'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    report=analyze(args.attempt)
    output=Path(args.output)
    if output.exists():raise ValueError('Retain prior station analysis report')
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt,build_result(args.attempt,report))


if __name__=='__main__': main()
