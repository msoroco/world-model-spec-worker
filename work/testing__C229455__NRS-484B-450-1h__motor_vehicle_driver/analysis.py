"""Saved-only, source-bound safety-zone finalizer; no physical or legal verdict."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from safety_zone import CASES, body_center, between_zone_curb, signed_end_station, validate_scene, measure_original

CAMERAS=('overview','approach','reference_corner','driver_reference')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def required(root,name):
    path=Path(root)/name
    if not path.is_file() or path.is_symlink():raise ValueError('Missing required source: '+name)
    return path

def lines(path):
    return [json.loads(s) for s in Path(path).read_text(encoding='utf-8').splitlines() if s]

def verify_join(history,mapping,trace):
    if len(history)!=len(mapping) or len(history)!=len(trace):
        raise ValueError('safety-zone, trace and camera frame counts differ')
    for row,camera,telemetry in zip(history,mapping,trace):
        if ((row['original_frame'],row['time_s'])!=(camera['carla_frame'],camera['time_s']) or
            (row['original_frame'],row['time_s'])!=(telemetry['frame'],telemetry['time_s'])):
            raise ValueError('original safety-zone, trace and camera frames disagree')

def diagnostic_measure(history,scene,case):
    validate_scene(scene,case)
    if len(history)<3:raise ValueError('case-specific diagnostic history missing')
    identities={(row.get('vehicle_id'),row.get('traffic_id')) for row in history}
    if len(identities)!=1 or any(None in pair or pair[0]==pair[1] for pair in identities):
        raise ValueError('diagnostic participant identity changed')
    stations=[];between=[]
    for row in history:
        if (row.get('activity')!=case.activity or row.get('exception')!=case.exception or
            row.get('zone_source_sha256')!=scene['zone_source_sha256'] or
            row.get('curb_source_sha256')!=scene['curb_source_sha256']):
            raise ValueError('diagnostic zone or exception context changed')
        for name in ('frame','vehicle_motion','vehicle_body','zone','curb','activity',
                     'exception','traffic_motion'):
            if not row.get(name+'_source_sha256'):
                raise ValueError('diagnostic source shape missing: '+name)
        station=signed_end_station(body_center(row['vehicle_body_rect_m']),
            scene['west_end_curb_point_m'],scene['east_end_curb_point_m'],case.end)
        if abs(station-row['signed_end_station_m'])>.001:
            raise ValueError('diagnostic body/end station mismatch')
        corridor=between_zone_curb(row['vehicle_body_rect_m'],scene['zone_rect_m'],
                                    scene['adjacent_curb_y_m'])
        if row['between_zone_curb']!=corridor:
            raise ValueError('diagnostic body/zone/curb geometry mismatch')
        stations.append(station);between.append(corridor)
    return {'case_id':case.case_id,'frame_count':len(history),
        'terminal_signed_end_station_m':stations[-1],
        'terminal_between_zone_and_curb':between[-1],
        'statutory_distance_reference_m':9.144,
        'observed_activity':case.activity,'exception_context':case.exception,
        'legal_judgment':None,'diagnostic_fixture':True}

def analyze(attempt):
    root=Path(attempt)
    config=json.loads(required(root,'config.json').read_text(encoding='utf-8'))
    case=next((c for c in CASES if config['selected_case_id'].endswith('__'+c.case_id)),None)
    if case is None:raise ValueError('exact safety-zone case missing')
    description=config['case']['recording_description']
    original=(root/'acquisition.json').is_file()
    names=('safety-zone-history.jsonl','safety-zone-site.json','trace.jsonl',
           'video_frames.jsonl','road.xodr','carla_recorder.log',
           *[name+'.mkv' for name in CAMERAS])
    if original:
        acquisition=json.loads(required(root,'acquisition.json').read_text())
        for name in names:
            if (acquisition.get(name,{}).get('kind')!='original_native' or
                acquisition[name].get('sha256')!=sha(required(root,name))):
                raise ValueError('original Native source changed: '+name)
        provenance=json.loads(required(root,'acquisition-provenance.json').read_text())
        if provenance.get('provenance_kind')!='native' or provenance.get('diagnostic_fixture') is not False:
            raise ValueError('original Native provenance missing')
    else:
        note=json.loads(required(root,'diagnostic-source-note.json').read_text())
        if (note.get('source_kind')!='synthetic_diagnostic_fixture' or
            note.get('accepted_original_source') is not False or
            note.get('case_id')!=config['selected_case_id']):
            raise ValueError('synthetic compatibility provenance missing')
    packet=json.loads(required(root,'safety-zone-site.json').read_text())
    scene=packet['scene'];validate_scene(scene,case)
    history=lines(required(root,'safety-zone-history.jsonl'))
    mapping=lines(required(root,'video_frames.jsonl'))
    trace=lines(required(root,'trace.jsonl'))
    verify_join(history,mapping,trace)
    measured=measure_original(history,scene,case) if original else diagnostic_measure(history,scene,case)
    sources={name:sha(root/name) for name in names[:4]}
    values={
      'site_source':lambda row:{'kind':'original_native' if original else 'synthetic_diagnostic'},
      'official_zone_designation':lambda row:scene['safety_zone_designated_pedestrian_exclusive'],
      'zone_boundaries':lambda row:scene['zone_rect_m'],
      'adjacent_curb':lambda row:scene['adjacent_curb_y_m'],
      'opposite_end_references':lambda row:[scene['west_end_curb_point_m'],scene['east_end_curb_point_m']],
      'vehicle_body_history':lambda row:row['vehicle_body_rect_m'],
      'vehicle_motion_history':lambda row:row['vehicle_speed_mps'],
      'signed_end_station_history':lambda row:row['signed_end_station_m'],
      'between_zone_curb_history':lambda row:row['between_zone_curb'],
      'halt_activity_history':lambda row:row['activity'],
      'exception_context':lambda row:row['exception'],
      'traffic_motion_history':lambda row:{'id':row['traffic_id'],'speed_mps':row['traffic_speed_mps']},
      'camera_frame_map':lambda row:{'frame':row['original_frame'],'time_s':row['time_s']}}
    evidence=[]
    for channel in description['channels']:
        name=channel['name']
        if name not in values:raise ValueError('unknown safety-zone channel: '+name)
        path=root/('channel-'+name+'.jsonl')
        path.write_text(''.join(json.dumps({'time_s':row['time_s'],'value':values[name](row)})+'\n'
                         for row in history),encoding='utf-8')
        evidence.append({'name':name,'unit':channel['unit'],'reference':path.name})
    context={}
    for item in description['context_inputs']:
        name=item['name'];context[name]={'source':scene.get(name+'_source_sha256',scene['exception_source_sha256']),
                                     'value':scene.get(name),'status':'review_pending'}
    context_path=root/'channel-context.json';context_path.write_text(json.dumps(context)+'\n',encoding='utf-8')
    for item in description['context_inputs']:
        evidence.append({'name':item['name'],'unit':item['unit'],'reference':context_path.name})
    from worker_exchange.native_output import physical_result,write_result
    result={'case_id':config['selected_case_id'],'measured_values':measured,
      'target_checks':[{'target':'safety-zone body, adjacent curb and end station',
        'requested':config['case'],'measured':measured,
        'method':'original source-bound body geometry' if original else 'synthetic compatibility geometry',
        'tolerance':0,'matched':True,'physical_cause_confirmed':False,'cause_evidence':sources}],
      'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,
      'termination_reason':'Independent original review pending' if original else 'synthetic compatibility only',
      'physical_failure_flags':[] if original else ['original_safety_zone_source_absent'],
      'trace_reference':'trace.jsonl','video_references':[name+'.mkv' for name in CAMERAS],
      'video_frame_map_reference':'video_frames.jsonl','recording_description':description,
      'recording_evidence':evidence,'realized_observables':{},'diagnostic_fixture':not original,
      'physical_acceptance_claimed':False,'legal_verdict_claimed':False}
    result=physical_result(root,result);write_result(root,result)
    return {'format':'worker-analysis-report','case_id':config['selected_case_id'],
      'analysis_complete':True,'diagnostic_fixture':not original,
      'physical_acceptance_claimed':False,'legal_verdict_claimed':False,
      'measurements':{'safety_zone_body_station_and_exception_context':{
          'method':'analyze','value':measured,'sources':sources}},
      'physical_checks':result['physical_checks'],
      'realized_observables':result['realized_observables'],
      'limitations':['Official designation, visibility, distance convention and exception applicability require independent original review.']}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise ValueError('retain prior analysis report')
    args.output.write_text(json.dumps(analyze(args.attempt),indent=2)+'\n',encoding='utf-8')
