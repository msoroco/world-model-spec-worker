"""Saved-only original controlled-access crossing and notice measurements."""
import argparse
import hashlib
import json
from pathlib import Path
from package_spec import CAMERA_NAMES
from access_probe import measure

def need(ok,message):
    if not ok:raise ValueError(message)
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def source(root,name):
    path=root/name
    if not path.is_file() or path.is_symlink():raise ValueError('Missing required source: '+name)
    return path

def source_sealed_access_measurement(value):
    return value

def analyze(attempt):
    root=Path(attempt).resolve()
    config=json.loads(source(root,'config.json').read_text())
    case=config['selected_case_id']
    receipt=json.loads(source(root,'original-source-receipt.json').read_text())
    diagnostic=receipt.get('diagnostic_fixture') is True
    need(receipt.get('source_kind')==('synthetic_diagnostic_fixture' if diagnostic else 'original_native_capture') and receipt.get('case_id')==case,'exact original/diagnostic source receipt differs')
    names={'history_sha256':'access-history.json','trace_sha256':'trace.jsonl','frame_map_sha256':'video_frames.jsonl','measurement_sha256':'access-measurement.json'}
    for key,name in names.items():need(receipt.get(key)==sha(source(root,name)),'sealed access source differs: '+key)
    history=json.loads(source(root,'access-history.json').read_text())
    rows=history['samples']
    trace=[json.loads(line) for line in source(root,'trace.jsonl').read_text().splitlines()]
    frame_map=[json.loads(line) for line in source(root,'video_frames.jsonl').read_text().splitlines()]
    need(history.get('assignment_id')==config['assignment_id'] and history.get('case_id')==case and len(rows)==len(trace)==len(frame_map) and len(rows)>=3,'access source row count or identity differs')
    for index,(row,mapped,motion) in enumerate(zip(rows,frame_map,trace)):
        need(row['frame']==mapped['video_frame']==index and mapped['native_frame']==mapped['carla_frame']==motion['frame']==row['original_frame'] and row['time_s']==mapped['time_s']==motion['time_s'] and abs(motion['speed_mps']-row['speed_mps'])<1e-6 and row['driver_id']==history['driver_actor_id'],'original vehicle/trace/video frame join differs')
        if not diagnostic:need(row.get('boundary_xy')==row['position_xyz_m'][:2],'original boundary coordinate differs from Native pose')
    site={key:history[key] for key in ('authority_source','highway_source','boundary_source','controlled_access_determination','boundary_x_m','indicated_points','official_notice_source')}
    site['vehicle_id']=history['driver_actor_id']
    frames=[{'original_frame':row['original_frame'],'time_s':row['time_s'],'vehicle_id':row['driver_id'],'xy':row['boundary_xy'],'source_ref':row['source_ref']} for row in rows]
    measured=measure(site,frames)
    need(json.loads(source(root,'access-measurement.json').read_text())==measured,'original access measurement differs from source frames')
    values={
      'controlled_access_authority':{'determination':history['controlled_access_determination'],'authority_source':history['authority_source']},
      'public_highway_boundary':{'public_highway':history['public_highway'],'boundary_x_m':history['boundary_x_m'],'highway_source':history['highway_source'],'boundary_source':history['boundary_source']},
      'official_erected_devices':{'authority_designated':history['authority_designated_devices'],'official_notice_source':history['official_notice_source'],'devices':[{'device_id':p['device_id'],'source':p['device_source'],'erected':p['erected']} for p in history['indicated_points']]},
      'designated_access_points':{'points':history['indicated_points']},
      'notice_visibility':{'point':history['target_point'],'source_notice_visible':history['target_point']['notice_visible'],'pixel_review_pending':True},
      'vehicle_boundary_crossing':{'crossings':measured['crossings'],'all_at_visible_indicated_points':measured['all_crossings_at_indicated_points']},
      'vehicle_motion':{'first_position_m':trace[0]['position_m'],'last_position_m':trace[-1]['position_m'],'maximum_speed_mps':max(row['speed_mps'] for row in rows)}}
    contract_sources={name:sha(source(root,name)) for name in ('access-history.json','original-source-receipt.json','trace.jsonl')}
    measurements={name:{'method':'source_sealed_access_measurement','value':source_sealed_access_measurement(value),'sources':contract_sources} for name,value in values.items()}
    evidence=[]
    for channel in config['case']['recording_description']['channels']:
        name=channel['name'];output=root/('channel-'+name+'.jsonl')
        content=''.join(json.dumps({'time_s':row['time_s'],'value':row['boundary_xy'] if name=='vehicle_boundary_crossing' else row['position_xyz_m'] if name=='vehicle_motion' else values[name]},sort_keys=True)+'\n' for row in rows)
        if output.exists():need(output.read_text()==content,'derived channel differs from saved source')
        else:output.write_text(content)
        evidence.append({'name':name,'unit':channel['unit'],'reference':output.name})
    context=root/'channel-reviewed_controlled_access_site.json'
    content=json.dumps({'reviewed_controlled_access_site':{'reviewed_site_sha256':history['reviewed_site_sha256'],'authority_source':history['authority_source'],'official_notice_source':history['official_notice_source']}},sort_keys=True)+'\n'
    if context.exists():need(context.read_text()==content,'reviewed site context differs')
    else:context.write_text(content)
    evidence.append({'name':'reviewed_controlled_access_site','unit':'source record','reference':context.name})
    target={'target':'source-reviewed controlled-access boundary crossing','requested':history['requested_direction'],'measured':measured['crossings'],'method':'original Native pose plus separate authority and device source','tolerance':0,'matched':bool(measured['crossings']),'physical_cause_confirmed':False,'cause_evidence':contract_sources}
    from worker_exchange.native_output import physical_result,write_result
    result={'case_id':case,'measured_values':values,'target_checks':[target],'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,'termination_reason':'saved physical and source review pending','physical_failure_flags':['physical_acceptance_unverified'],'trace_reference':'trace.jsonl','video_references':[x+'.mkv' for x in CAMERA_NAMES],'video_frame_map_reference':'video_frames.jsonl','recording_description':config['case']['recording_description'],'recording_evidence':evidence,'realized_observables':{},'diagnostic_fixture':diagnostic,'physical_acceptance_claimed':False,'legal_verdict_claimed':False}
    result=physical_result(root,result);write_result(root,result)
    return {'format':'worker-analysis-report','case_id':case,'analysis_complete':True,'diagnostic_fixture':diagnostic,'physical_acceptance_claimed':False,'legal_verdict_claimed':False,'measurements':measurements,'physical_checks':result['physical_checks'],'realized_observables':result['realized_observables'],'limitations':['Map road type cannot establish controlled-access status; independent authority and official device notice review required.']}
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise ValueError('retain prior analysis report')
    args.output.write_text(json.dumps(analyze(args.attempt),indent=2)+'\n')
