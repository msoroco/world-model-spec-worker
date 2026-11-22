"""Saved-only, source-hashed measurements for the manual-wheelchair branch."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from runner import bounds,gap,wheelchair_body

SOURCES=('encounter-history.jsonl','intersection-context.json')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verified(attempt,name,acquisition):
    path=Path(attempt)/name;source=acquisition.get(name,{})
    if not path.is_file():raise ValueError('Missing required source: '+name)
    if source.get('kind')!='original_native' or source.get('sha256')!=sha(path):
        raise ValueError('missing or stale original Native source: '+name)
    return path


def measure(attempt):
    attempt=Path(attempt);acquisition=json.loads((attempt/'acquisition.json').read_text())
    paths={name:verified(attempt,name,acquisition) for name in SOURCES}
    context=json.loads(paths['intersection-context.json'].read_text())
    if not context.get('route_source') or not context.get('manual_wheelchair_asset_source'):
        raise ValueError('original route or wheelchair asset identity absent')
    rows=[json.loads(line) for line in paths['encounter-history.jsonl'].read_text().splitlines() if line.strip()]
    if len(rows)<2:raise ValueError('insufficient original encounter history')
    previous=None;surface=[];ttc=[];brakes=[];contacts=[]
    for row in rows:
        frame=row.get('frame');time_s=row.get('time_s')
        if type(frame) is not int or type(time_s) not in (int,float) or not math.isfinite(time_s):
            raise ValueError('invalid original frame or time')
        if previous and (frame<=previous[0] or time_s<=previous[1]):
            raise ValueError('original encounter frame/time order changed')
        previous=(frame,time_s)
        person=row.get('person',{});chair=row.get('manual_wheelchair',{})
        combined=wheelchair_body(person,chair)
        ego=row.get('ego_body_vertices_m')
        bounds(ego)
        measured_gap=gap(ego,combined)
        if abs(row.get('surface_gap_m',float('inf'))-measured_gap)>.05:
            raise ValueError('reported surface gap differs from original bodies')
        speed=row.get('ego_speed_mps');brake=row.get('ego_brake')
        if type(speed) not in (int,float) or not math.isfinite(speed) or speed<0 or type(brake) not in (int,float) or not 0<=brake<=1:
            raise ValueError('original speed or brake control missing')
        ex_right=bounds(ego)[2];px_left=bounds(combined)[0]
        time_to_path=max(px_left-ex_right,0)/speed if speed>0 else None
        if time_to_path is not None:ttc.append(time_to_path)
        surface.append(measured_gap)
        if brake>0:brakes.append(frame)
        if row.get('contact_event') is True:contacts.append(frame)
        elif row.get('contact_event') is not False:raise ValueError('original contact event missing')
    return {'format':'worker-manual-wheelchair-measurements',
            'frame_count':len(rows),'minimum_surface_gap_m':min(surface),
            'minimum_time_to_path_s':min(ttc) if ttc else None,
            'first_brake_frame':brakes[0] if brakes else None,
            'contact_frames':contacts,
            'sources':{name:acquisition[name]['sha256'] for name in SOURCES},
            'legal_due_care_verdict':'unresolved'}


def build_report(attempt):
    value=measure(attempt)
    return {'format':'worker-analysis-report',
            'measurements':{'wheelchair_due_care_measurement':{
                'value':value,'method':'measure','sources':value['sources']}},
            'limitations':['Physical source identity and legal due care require independent review.'],
            'analysis_complete':True,'legal_verdict_claimed':False}


def saved_result(attempt,report):
    from worker_exchange.native_output import physical_result,validate_result
    attempt=Path(attempt)
    config=json.loads((attempt/'config.json').read_text())
    construction=json.loads((attempt/'construction.json').read_text())
    planned=construction['recording_description']
    acquisition=json.loads((attempt/'acquisition.json').read_text())
    history=verified(attempt,'encounter-history.jsonl',acquisition)
    rows=[json.loads(line) for line in history.read_text().splitlines() if line.strip()]
    frame_map=verified(attempt,'video_frames.jsonl',acquisition)
    frames=[json.loads(line) for line in frame_map.read_text().splitlines() if line.strip()]
    if len(frames)!=len(rows):raise ValueError('Original encounter and camera frame counts differ')
    if any((frame.get('carla_frame'),frame.get('time_s'))!=(row.get('frame'),row.get('time_s'))
           for row,frame in zip(rows,frames)):
        raise ValueError('Original encounter and camera frame identities differ')
    context=json.loads(verified(attempt,'intersection-context.json',acquisition).read_text())
    output=attempt/'channels';output.mkdir(exist_ok=True)
    streams={
      'ego_body_history':[(r['time_s'],r['ego_body_vertices_m']) for r in rows],
      'wheelchair_person_body_history':[(r['time_s'],r['person']) for r in rows],
      'manual_wheelchair_body_history':[(r['time_s'],r['manual_wheelchair']) for r in rows],
      'ego_speed_and_brake_history':[(r['time_s'],{'speed_mps':r['ego_speed_mps'],'brake':r['ego_brake']}) for r in rows],
      'contact_history':[(r['time_s'],{'contact_event':r['contact_event'],'surface_gap_m':r['surface_gap_m']}) for r in rows],
      'pedestrian_path_and_speed_history':[(r['time_s'],{'body_vertices_m':r['person']['body_vertices_m'],
             'speed_mps':r['pedestrian_speed_mps']}) for r in rows],
      'contact_events':[(r['time_s'],r['contact_event']) for r in rows],
      'intersection_geometry':[(r['time_s'],context) for r in rows],
      'camera_frame_map':[(r['time_s'],frame) for r,frame in zip(rows,frames)]}
    evidence=[]
    for channel in planned['channels']:
        name=channel['name']
        if name not in streams:raise ValueError('Unsupported declared recording channel: '+name)
        path=output/(name+'.jsonl')
        with path.open('x') as stream:
            for time_s,value in streams[name]:
                stream.write(json.dumps({'time_s':time_s,'value':value},allow_nan=False)+'\n')
        evidence.append({'name':name,'unit':channel['unit'],'reference':str(path.relative_to(attempt))})
    context_path=output/'context.json'
    with context_path.open('x') as stream:
        stream.write(json.dumps({'intersection_context':context,
          'wheelchair_identity_context':{'source_sha256':acquisition['encounter-history.jsonl']['sha256'],
          'manual_wheelchair_asset_source':context['manual_wheelchair_asset_source']}},allow_nan=False)+'\n')
    for item in planned['context_inputs']:
        evidence.append({'name':item['name'],'unit':item['unit'],'reference':str(context_path.relative_to(attempt))})
    value=report['measurements']['wheelchair_due_care_measurement']['value']
    no_contact=not value['contact_frames']
    result={'case_id':config['selected_case_id'],'measured_values':value,
      'target_checks':[{'target':'observed pedestrian encounter without contact','requested':True,
          'measured':no_contact,'method':'measure','tolerance':0,'matched':no_contact,
          'physical_cause_confirmed':False,'cause_evidence':value['sources']}],
      'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,
      'termination_reason':'Saved source assessment pending physical review',
      'physical_failure_flags':[],'trace_reference':'trace.jsonl',
      'video_references':['overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv'],
      'video_frame_map_reference':'video_frames.jsonl','recording_description':planned,
      'recording_evidence':evidence,'realized_observables':{}}
    result=physical_result(attempt,result)
    validate_result(result)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True);args=parser.parse_args()
    report=build_report(args.attempt)
    result=saved_result(args.attempt,report)
    report['physical_checks']=result['physical_checks']
    report['realized_observables']=result['realized_observables']
    with (Path(args.attempt)/'result.json').open('x') as stream:
        stream.write(json.dumps(result,indent=2)+'\n')
    with Path(args.output).open('x') as stream:
        stream.write(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
