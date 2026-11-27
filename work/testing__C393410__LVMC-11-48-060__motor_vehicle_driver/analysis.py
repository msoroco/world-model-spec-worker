"""Saved-only source-bound route finalizer; no legal verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from route_measure import measure

CAMERAS = ('overview','approach','reference_corner','driver_reference')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def required(root: Path, name: str) -> Path:
    path = root/name
    if not path.is_file():
        raise ValueError('Missing required source: '+name)
    return path


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def measure_route(source: Path) -> dict:
    return measure(source)


def measure_scope(source: Path) -> dict:
    return measure(source)


def measure_pickup(source: Path) -> dict:
    m=measure(source);return {'pick_up_required_enroute':m['enroute_purpose_kind']=='pick_up' and m['enroute_activity_observed'] and m['required_enroute_reviewed'],'legal_verdict':'unresolved'}


def measure_delivery(source: Path) -> dict:
    m=measure(source);return {'delivery_required_enroute':m['enroute_purpose_kind']=='delivery' and m['enroute_activity_observed'] and m['required_enroute_reviewed'],'legal_verdict':'unresolved'}


def measure_essential(source: Path) -> dict:
    m=measure(source);return {'essential_use_required_enroute':m['enroute_purpose_kind']=='essential_use' and m['enroute_activity_observed'] and m['required_enroute_reviewed'],'legal_verdict':'unresolved'}


def measure_route_control(source: Path) -> dict:
    m=measure(source);return {'local_or_designated_control':not m['destination_truck_route_observed'] or m['intervening_designation']=='truck_route','legal_verdict':'unresolved'}


def analyze(attempt: Path, output: Path) -> dict:
    attempt,output=Path(attempt).resolve(),Path(output).resolve()
    config=json.loads(required(attempt,'config.json').read_text())
    case_id=config['selected_case_id']
    source=required(attempt,'original-route-observations.json')
    packet=json.loads(source.read_text())
    receipt=json.loads(required(attempt,'original-route-receipt.json').read_text())
    if (packet.get('case_id')!=case_id or receipt.get('case_id')!=case_id
            or receipt.get('source_sha256')!=sha(source) or receipt.get('fps')!=20):
        raise ValueError('Original route receipt identity or source hash differs')
    measurement=measure_route(source)
    frames=packet['frames']
    if receipt.get('frame_count')!=len(frames):
        raise ValueError('Original route frame count differs')
    frame_map=rows(required(attempt,'video_frames.jsonl'))
    trace=rows(required(attempt,'trace.jsonl'))
    if packet.get('diagnostic_fixture') is False and packet.get('original_trace_id')!='Native:'+sha(attempt/'trace.jsonl'):
        raise ValueError('Original route packet trace source differs')
    if len(frames)!=len(frame_map) or len(frames)!=len(trace):
        raise ValueError('Original route streams differ')
    for index,(frame,mapped,row) in enumerate(zip(frames,frame_map,trace)):
        if (mapped.get('video_frame')!=index or frame.get('frame')!=mapped.get('carla_frame')
                or frame['frame']!=mapped.get('native_frame') or row.get('frame')!=frame['frame']
                or abs(frame['time_s']-mapped.get('time_s',-1))>1e-4
                or abs(frame['time_s']-row.get('time_s',-1))>1e-4):
            raise ValueError('Original route frame/time join differs')
    for camera in CAMERAS: required(attempt,camera+'.mkv')
    description=config['case']['recording_description']
    channels=attempt/'channels';channels.mkdir(exist_ok=False)
    site=packet['site'];purpose=packet['enroute_purpose']
    values={
        'municipal_route_designation':lambda frame:{'municipal_jurisdiction_reviewed':site['municipal_jurisdiction_reviewed'],'truck_routes':site['truck_routes'],'intervening_street':site['intervening_street']},
        'ego_route_history':lambda frame:{'road_id':frame['road_id'],'street_designation':frame['street_designation'],'position_xy_m':frame['position_xy_m'],'ego_actor_id':frame['ego_actor_id']},
        'enroute_context':lambda frame:{'kind':purpose['kind'],'required_enroute_reviewed':purpose.get('required_enroute_reviewed',False),'activity_kind':frame.get('activity_kind'),'premises_source_sha256':purpose.get('premises_source_sha256')},
        'governing_controls':lambda frame:{'controls_reviewed':site['governing_controls_reviewed'],'chapter_scope_reviewed':site['chapter_scope_reviewed']}}
    evidence=[]
    for channel in description['channels']:
        name=channel['name']
        if name not in values: raise ValueError('Unimplemented route channel '+name)
        ref='channels/'+name+'.jsonl'
        with (attempt/ref).open('x') as stream:
            for frame in frames:
                stream.write(json.dumps({'time_s':frame['time_s'],'value':values[name](frame)},separators=(',',':'))+'\n')
        evidence.append({'name':name,'unit':channel['unit'],'reference':ref})
    context='channels/reviewed_truck_route_site.json'
    (attempt/context).write_text(json.dumps({'site_source_sha256':packet['site_source_sha256'],'legal_judgment':'unresolved'})+'\n')
    evidence.append({'name':'reviewed_truck_route_site','unit':'source','reference':context})
    native={'case_id':case_id,'measured_values':{'route':measurement},'target_checks':[{'target':'source-bound between-route passage and enroute context','requested':True,'measured':True,'method':'measure_route','tolerance':0,'matched':True,'physical_cause_confirmed':False,'cause_evidence':['original-route-observations.json']}],
        'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,'termination_reason':'Saved route measurement; physical and legal review pending','physical_failure_flags':[],'trace_reference':'trace.jsonl','video_references':[name+'.mkv' for name in CAMERAS],'video_frame_map_reference':'video_frames.jsonl','recording_description':description,'recording_evidence':evidence,'realized_observables':{}}
    (attempt/'result.json').write_text(json.dumps(native,indent=2,allow_nan=False)+'\n')
    report={'format':'worker-analysis-report','case_id':case_id,'measurements':{key:{'method':method.__name__,'sources':{'original-route-observations.json':sha(source),'original-route-receipt.json':sha(attempt/'original-route-receipt.json')},'value':method(source)} for key,method in [('scope',measure_scope),('pickup_context',measure_pickup),('delivery_context',measure_delivery),('essential_context',measure_essential),('route_control',measure_route_control)]},'limitations':['Original route designations, premises activity, Native motion and legal required-enroute judgment require independent review.']}
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();analyze(args.attempt,args.output)

if __name__=='__main__':main()
