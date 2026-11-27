"""Recorded-only divided-roadway source finalizer; no legal inference from requests."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from measure_median_turn import measure

CAMERAS=('overview','approach','reference_corner','driver_reference')
CHANNELS=('st.median_or_divider','st.roadway','rel.occupies','st.lane_direction',
          'drv.turning','drv.u_turn','st.intersection','drv.wrong_way','kin.position')
SOURCE_KEYS=('native_map_sha256','divider_geometry_sha256','roadway_direction_sha256',
             'physical_opening_sha256','vehicle_extent_sha256','ego_pose_source_sha256',
             'turn_annotation_sha256')
OUTPUT_KEYS=('physical_opening','crossing_section','authority_crossover',
             'semicircular_turn','u_turn','right_hand_roadway')

def require(ok,message):
    if not ok:raise ValueError(message)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def source_bound_divided_highway_turn(context,rows):
    return measure(context,rows)

def run(attempt,output):
    attempt,output=Path(attempt),Path(output)
    required=('original_divided_context.json','original_turn_annotations.json',
              'median-capture.jsonl','body_history.jsonl','video_frames.jsonl','trace.jsonl','capture/evidence.jsonl')
    for name in required:require((attempt/name).is_file(),'Missing required source: '+name)
    require(not output.exists(),'Choose a fresh analysis report')
    config=json.loads((attempt/'config.json').read_text())
    context=json.loads((attempt/required[0]).read_text())
    annotation=json.loads((attempt/required[1]).read_text())
    require(context.get('turn_annotation_sha256')==sha(attempt/required[1]),
            'Original turn annotation source hash changed')
    for key in SOURCE_KEYS:
        doc=context.get('source_documents',{}).get(key)
        require(isinstance(doc,str) and doc.startswith('original-') and '/' not in doc and '\\' not in doc,
                'Original source document missing: '+key)
        require((attempt/doc).is_file(),'Missing required source: '+doc)
        require(sha(attempt/doc)==context.get(key),'Original source document hash changed: '+key)
    if context.get('public_authority_crossover_established') in (True,False):
        key='public_authority_crossover_sha256';doc=context.get('source_documents',{}).get(key)
        require(isinstance(doc,str) and (attempt/doc).is_file() and sha(attempt/doc)==context.get(key),
                'Original public-authority document missing or changed')
    provenance_path=attempt/'acquisition-provenance.json'
    provenance=json.loads(provenance_path.read_text()) if provenance_path.is_file() else {}
    diagnostic=(os.environ.get('SCENARIO_DIAGNOSTIC_FIXTURE')=='1' or
                provenance.get('diagnostic_fixture') is True)
    require(context.get('assignment_id')==config['case_id'].rsplit('__',1)[0],
            'Divided-road assignment identity differs')
    if diagnostic:
        require(context.get('source_kind')=='synthetic_cpu_divided_highway_fixture',
                'Diagnostic fixture provenance missing')
        context['source_kind']='original_native_divided_highway_readback'
    else:
        require(context.get('source_kind')=='original_native_divided_highway_readback',
                'Original divided-highway source missing')
    rows=[json.loads(s) for s in (attempt/'median-capture.jsonl').read_text().splitlines() if s]
    bodies=[json.loads(s) for s in (attempt/'body_history.jsonl').read_text().splitlines() if s]
    frames=[json.loads(s) for s in (attempt/'video_frames.jsonl').read_text().splitlines() if s]
    traces=[json.loads(s) for s in (attempt/'trace.jsonl').read_text().splitlines() if s]
    require(len(rows)==len(bodies)==len(frames)==len(traces)==600,
            'Original turn, body, video and Native trace frame counts differ')
    require(len(annotation.get('frames',[]))==len(rows) and
            all(x.get('video_frame')==i and x.get('turn_mode') in ('none','left_turn','semicircular_turn','u_turn')
                for i,x in enumerate(annotation['frames'])),
            'Original frame-matched turn annotation missing')
    for i,row in enumerate(rows):
        mode=annotation['frames'][i]['turn_mode']
        body,frame,trace=bodies[i],frames[i],traces[i]
        require(row['native_frame']==body.get('frame')==frame.get('carla_frame')==trace.get('frame') and
                row['source_cameras']==frame.get('camera_native_frames') and
                abs(row['time_s']-body.get('time_s',-1))<1e-6 and
                abs(row['time_s']-frame.get('time_s',-1))<1e-6 and
                abs(row['time_s']-trace.get('time_s',-1))<1e-6,
                'Original median, body, video and Native frame join changed')
        require(abs(body['position_m'][0]-row['ego_center_x_m'])<1e-6 and
                abs(body['position_m'][1]-row['ego_center_y_m'])<1e-6 and
                abs(trace['position_m'][0]-row['ego_center_x_m'])<1e-6 and
                abs(trace['position_m'][1]-row['ego_center_y_m'])<1e-6 and
                abs(body['heading_deg']-row['observed_yaw_deg'])<1e-6,
                'Original median/body pose join changed')
        require(row.get('left_turn_active')==(mode=='left_turn') and
                row.get('semicircular_turn_active')==(mode=='semicircular_turn') and
                row.get('u_turn_active')==(mode=='u_turn'),
                'Observed Native turn annotation join changed')
    finding=source_bound_divided_highway_turn(context,rows)
    require(tuple(c['name'] for c in config['recording_description']['channels'])==CHANNELS,
            'Selected source channels changed')
    channels=attempt/'channels';channels.mkdir(exist_ok=False);evidence=[]
    for name in CHANNELS:
        path=channels/(name+'.jsonl')
        with path.open('x') as stream:
            for row in rows:
                if name=='st.median_or_divider':value={'median_y_m':context['median_y_m'],'opening_x_m':context['opening_x_m'],'divider_source_sha256':context['divider_geometry_sha256']}
                elif name=='st.roadway':value={'roadway_source_sha256':context['roadway_direction_sha256'],'observed_direction':row['roadway_direction']}
                elif name=='rel.occupies':value={'observed_ego_center_x_m':row['ego_center_x_m'],'observed_ego_center_y_m':row['ego_center_y_m'],'ego_length_m':row['ego_length_m'],'ego_width_m':row['ego_width_m']}
                elif name=='st.lane_direction':value={'roadway_direction':row['roadway_direction'],'source_sha256':context['roadway_direction_sha256']}
                elif name=='drv.turning':value={'left_turn':row['left_turn_active'],'semicircular_turn':row['semicircular_turn_active'],'turn_annotation_sha256':context['turn_annotation_sha256']}
                elif name=='drv.u_turn':value={'observed_u_turn':row['u_turn_active'],'turn_annotation_sha256':context['turn_annotation_sha256']}
                elif name=='st.intersection':value={'authority_established':context.get('public_authority_crossover_established'),'authority_source_sha256':context.get('public_authority_crossover_sha256')}
                elif name=='drv.wrong_way':value={'observed_opposite_roadway':row['roadway_direction']=='opposite'}
                else:value={'x_m':row['ego_center_x_m'],'y_m':row['ego_center_y_m']}
                stream.write(json.dumps({'time_s':row['time_s'],'value':value})+'\n')
        evidence.append({'name':name,'unit':'structured','reference':'channels/'+path.name})
    from worker_exchange.native_output import physical_result,write_result
    result={'case_id':config['case_id'],'measured_values':finding,
            'target_checks':[{'target':'source-observed turn and median footprint','requested':config.get('requested_crossing_station_m'),
                              'measured':finding['median_crossing_center_x_range_m'],
                              'method':'original divided-road survey, per-frame Native footprint and turn-source join',
                              'tolerance':'source and vehicle-footprint accuracy require original review','matched':False,
                              'physical_cause_confirmed':False,'cause_evidence':list(required)}],
            'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,'accepted':False,
            'termination_reason':'Original source measured; physical, pixel and legal review pending',
            'physical_failure_flags':['original_source_and_physical_review_pending'],
            'trace_reference':'trace.jsonl','video_references':[name+'.mkv' for name in CAMERAS]+['raw.mkv'],
            'video_frame_map_reference':'video_frames.jsonl','recording_description':config['recording_description'],
            'recording_evidence':evidence,'realized_observables':{},
            'physical_acceptance_claimed':False,'legal_verdict_claimed':False}
    write_result(attempt,physical_result(attempt,result))
    sources={name:sha(attempt/name) for name in required}
    sources.update({doc:sha(attempt/doc) for doc in context['source_documents'].values()})
    report={'format':'worker-analysis-report','case_id':config['case_id'],
            'measurements':{key:{'method':'source_bound_divided_highway_turn','value':finding,'sources':sources}
                            for key in OUTPUT_KEYS},
            'source_complete':True,'physical_or_legal_acceptance':False}
    output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(json.dumps(run(a.attempt,a.output),sort_keys=True))
