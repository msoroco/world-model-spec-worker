"""Finalize an exact right-pass saved attempt from retained raw Native sources."""
import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path

import prepare_raw
from audit_physical_motion import audit as audit_motion


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def require(root,name):
    path=Path(root)/name
    if not path.is_file():raise ValueError('Missing required source: '+name)
    return path
def rows(root,name):
    return [json.loads(x) for x in require(root,name).read_text().splitlines() if x.strip()]


def measure_pass_clearance(measures):
    return measures['minimum_pass_body_surface_gap_m']


def measure_time_to_conflict(measures):
    values=[row['time_to_lead_center_s'] for row in measures['observations']
            if row['time_to_lead_center_s'] is not None]
    if not values:raise ValueError('No observed positive closing motion')
    return min(values)


def motion_fields(kind,motion,source_hashes):
    """Translate independent motion evidence without deciding legal safety."""
    if kind=='synthetic_native_sample':
        if motion is not None:raise ValueError('Synthetic motion cannot be original review')
        return {'maneuver_completed':False,
                'provenance_kind':'synthetic_local_diagnostic',
                'check':{'status':'unverified',
                    'method':'synthetic diagnostic cannot establish original right-pass motion',
                    'sources':source_hashes,
                    'missing_evidence':['original Native motion'],
                    'legal_verdict_claimed':False,'physical_causation_claimed':False}}
    if kind!='original_native' or not isinstance(motion,dict) or \
       motion.get('source_kind')!='original_native' or \
       motion.get('status') not in ('met','not_met','unverified') or \
       not motion.get('method') or not motion.get('sources'):
        raise ValueError('Original motion audit missing or unbound')
    status=motion['status']
    if motion.get('maneuver_completed')!=(status=='met'):
        raise ValueError('Original motion completion differs from audit')
    return {'maneuver_completed':status=='met','provenance_kind':'native',
            'check':{'status':status,'method':motion['method'],
                'sources':motion['sources'],
                'missing_evidence':motion.get('missing_evidence',[]),
                'legal_verdict_claimed':False,'physical_causation_claimed':False}}


def finalize(attempt,output):
    attempt,output=Path(attempt),Path(output)
    if output.exists() or (attempt/'result.json').exists() or (attempt/'channels').exists():
        raise ValueError('Retain previous finalization; use a fresh saved attempt')
    for name in ('construction.json','config.json','right-pass-road.xodr',
                 'requested-tracks.jsonl','native-map-readback.json',
                 'native-capture-report.json','native-raw-actors.jsonl',
                 'video_frames.jsonl','trace.jsonl','capture/evidence.jsonl'):
        require(attempt,name)
    cfg=json.loads((attempt/'config.json').read_text())
    construction=json.loads((attempt/'construction.json').read_text())
    if (cfg['selected_case_id']!=cfg['case_id'] or
        construction['case_id']!=cfg['case_id']):
        raise ValueError('Selected right-pass case identity differs')
    actors=rows(attempt,'native-raw-actors.jsonl')
    trace=rows(attempt,'trace.jsonl')
    frames=rows(attempt,'video_frames.jsonl')
    if len(actors)!=len(trace) or len(actors)!=len(frames) or len(actors)!=240:
        raise ValueError('Selected right-pass source frame count differs')
    kind=actors[0]['source_kind']
    if kind not in ('synthetic_native_sample','original_native'):
        raise ValueError('Unknown Native right-pass source kind')
    for i,(actor,point,frame) in enumerate(zip(actors,trace,frames)):
        ego=actor['ego'];native=actor['native_frame'];t=actor['time_s']
        if (actor['frame']!=i or frame['video_frame']!=i or
            frame['native_frame']!=native or frame['carla_frame']!=native or
            point['frame']!=native or
            point['position_m']!=ego['center_native_xyz_m'] or
            point['speed_mps']!=ego['speed_mps'] or
            abs(point['time_s']-t)>1e-5 or abs(frame['time_s']-t)>1e-5 or
            kind!=actor['source_kind']):
            raise ValueError('Selected right-pass Native trace/frame join differs at '+str(i))
    prepared=attempt/'prepared-sources'
    if prepared.exists():
        # Saved processing stages retained acquisition from a prior diagnostic
        # finalization. Its prepared outputs are derived and must be rebuilt
        # from the staged raw sources, never reused as evidence.
        if not prepared.is_dir() or {p.name for p in prepared.iterdir()} != {
                'preparation-receipt.json', 'right-pass-measures.json'}:
            raise ValueError('Unexpected prior derived preparation inventory')
        shutil.rmtree(prepared)
    receipt=prepare_raw.prepare(attempt,attempt,prepared,
                                synthetic_cpu=kind=='synthetic_native_sample')
    measures=json.loads((prepared/'right-pass-measures.json').read_text())
    source_hashes={name:sha(attempt/name) for name in
        ('native-raw-actors.jsonl','video_frames.jsonl','native-map-readback.json',
         'trace.jsonl','capture/evidence.jsonl')}
    clearance=measure_pass_clearance(measures)
    ttc=measure_time_to_conflict(measures)
    motion=audit_motion(attempt) if kind=='original_native' else None
    motion_summary=motion_fields(kind,motion,source_hashes)
    measurement_report={'format':'c146314-210-2-saved-analysis-v1',
        'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
        'measurements':{
            'measured_pass_body_clearance_m':{
                'method':'measure_pass_clearance','value':clearance,
                'sources':{name:source_hashes[name] for name in
                    ('native-raw-actors.jsonl','video_frames.jsonl')}},
            'minimum_positive_time_to_lead_center_s':{
                'method':'measure_time_to_conflict','value':ttc,
                'sources':{name:source_hashes[name] for name in
                    ('native-raw-actors.jsonl','video_frames.jsonl')}}},
        'source_kind':kind,'physical_acceptance_claimed':False,
        'legal_verdict_claimed':False}
    channels=attempt/'channels';channels.mkdir()
    evidence=[]
    values={
        'ego_pose':[{'center_xyz_m':row['ego']['center_native_xyz_m'],
                     'heading_deg':row['ego']['yaw_deg'],
                     'body_xyz_m':row['ego']['body_native_xyz_m']} for row in actors],
        'ego_speed':[row['ego']['speed_mps'] for row in actors],
        'right_side_pass_lateral_clearance':[
            row['observed_body_surface_gap_m'] for row in measures['observations']],
        'four_source_views':[True]*240}
    for channel in construction['recording_description']['channels']:
        name=channel['name']
        if name not in values:raise ValueError('Unknown recorded right-pass channel: '+name)
        path=channels/(name+'.jsonl')
        path.write_text(''.join(json.dumps({'time_s':row['time_s'],'value':value},
                            allow_nan=False)+'\n' for row,value in zip(actors,values[name])))
        evidence.append({'name':name,'unit':channel['unit'],
                         'reference':'channels/'+path.name})
    context=attempt/'right-pass-context.json'
    context.write_text(json.dumps({'right_pass_map_readback':{
        'source':'native-map-readback.json',
        'sha256':source_hashes['native-map-readback.json']}},indent=2)+'\n')
    evidence.append({'name':'right_pass_map_readback','unit':'structured',
                     'reference':context.name})
    requested=cfg['requested_nominal_body_gap_m']
    match=abs(clearance-requested)<=.5
    result={'case_id':cfg['case_id'],
        'measured_values':{'measured_pass_body_clearance_m':clearance,
                           'minimum_positive_time_to_lead_center_s':ttc},
        'target_checks':[{'target':'observed right-side pass body clearance',
            'requested':requested,'measured':clearance,
            'method':'observed Native convex body gap during right-side overtake',
            'tolerance':'0.5 m engineering request tolerance; not a legal safety limit',
            'matched':match,'physical_cause_confirmed':False,
            'cause_evidence':['native-raw-actors.jsonl','video_frames.jsonl']}],
        'setup_confirmed':False,'behavior_attempted':False,
        'maneuver_completed':motion_summary['maneuver_completed'],
        'termination_reason':'240 source frames; legal safety and pixel review pending',
        'physical_failure_flags':['Original right-pass safety and pixels unreviewed'],
        'physical_checks':{'maneuver':motion_summary['check']},
        'trace_reference':'trace.jsonl',
        'video_references':[name+'.mkv' for name in
            ('overview','approach','reference_corner','driver_reference')],
        'video_frame_map_reference':'video_frames.jsonl',
        'recording_description':construction['recording_description'],
        'recording_evidence':evidence,
        'realized_observables':{'measured_pass_body_clearance_m':{
            'value':clearance,'unit':'m','method':'retained Native body geometry',
            'time_window':'12 s diagnostic window','statistic':'minimum pass overlap gap',
            'reference':'native-raw-actors.jsonl'}},
        'provenance_kind':motion_summary['provenance_kind'],
        'accepted':False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    output.write_text(json.dumps(measurement_report,indent=2,allow_nan=False)+'\n')
    (attempt/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return measurement_report


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--attempt',required=True)
    p.add_argument('--output',required=True)
    a=p.parse_args()
    print(json.dumps(finalize(a.attempt,a.output),sort_keys=True))
