"""Selected saved lamp analysis. A synthetic fixture tests software shape only."""
import argparse
import hashlib
import json
from pathlib import Path

VIEWS=('overview','approach','reference_corner','driver_reference')
SOURCES=('native-rows.jsonl','lamp-review.jsonl','parking-context.json',
         'video_frames.jsonl','trace.jsonl','capture/evidence.jsonl')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]

def measure_parked_lamps(attempt):
    attempt=Path(attempt)
    native=rows(attempt/'native-rows.jsonl')
    review=rows(attempt/'lamp-review.jsonl')
    frames=rows(attempt/'video_frames.jsonl')
    trace=rows(attempt/'trace.jsonl')
    evidence=rows(attempt/'capture/evidence.jsonl')
    context=json.loads((attempt/'parking-context.json').read_text())
    if len(native)!=len(review)!=len(frames)!=len(trace)!=len(evidence) or len(native)!=600:
        raise ValueError('Complete 600-frame parked lamp observation required')
    for i,(n,r,f,t,e) in enumerate(zip(native,review,frames,trace,evidence)):
        if (n.get('frame')!=i or r.get('frame')!=i or f.get('video_frame')!=i
                or n.get('native_frame')!=f.get('native_frame')
                or t.get('frame')!=f.get('carla_frame')
                or any(abs(row.get('time_s',-999)-f['time_s'])>1e-6 for row in (n,r,t))
                or e.get('original_frame')!=f.get('native_frame')):
            raise ValueError('Original Native/frame/review identity differs')
        if n.get('observed_curb_lane_id')!=-2 or n.get('ego_speed_mps',999)>.1:
            raise ValueError('Original parked footprint window incomplete')
        if n.get('observed_beam_state') not in ('low_beam','high_beam'):
            raise ValueError('Original lighted headlamp readback missing')
        if r.get('parking_activity')!='parked' or r.get('aim_elevation_deg') is None or r.get('relative_intensity') is None:
            raise ValueError('Source-bound beam and parking review missing')
        if not isinstance(n.get('observed_footprint_xyz_m'),list) or len(n['observed_footprint_xyz_m'])<4:
            raise ValueError('Original full body footprint missing')
    state={r['observed_beam_state'] for r in native}
    if len(state)!=1 or context.get('cell_id')!='C276263' or context.get('road_grade_percent')!=4:
        raise ValueError('Exact slope or stable beam source absent')
    return {'frames':600,'observed_beam_state':state.pop(),
            'aim_elevation_deg_range':[min(r['aim_elevation_deg'] for r in review),max(r['aim_elevation_deg'] for r in review)],
            'relative_intensity_range':[min(r['relative_intensity'] for r in review),max(r['relative_intensity'] for r in review)],
            'parked_activity_frames':600,'road_grade_percent':4,
            'source_kind':context.get('source_kind')}

def finalize(attempt,output):
    attempt,output=Path(attempt),Path(output)
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain previous saved output; use a fresh attempt')
    for name in (*SOURCES,*(view+'.mkv' for view in VIEWS),'config.json','construction.json'):
        if not (attempt/name).is_file():
            raise ValueError('Missing required source: '+name)
    config=json.loads((attempt/'config.json').read_text())
    construction=json.loads((attempt/'construction.json').read_text())
    case=config['selected_case_id']
    if construction['case_id']!=case:
        raise ValueError('Selected case identity differs')
    context=json.loads((attempt/'parking-context.json').read_text())
    if context.get('case_id')!=case or context.get('source_kind') not in ('synthetic_cpu_fixture','original_native'):
        raise ValueError('Source context identity/provenance differs')
    measured=measure_parked_lamps(attempt)
    if measured['observed_beam_state']!=config['requested_beam_state']:
        raise ValueError('Observed beam differs from selected target')
    if context['source_kind']=='original_native':
        from finalize_original import finalize as finalize_original
        original=finalize_original(attempt,attempt/'source-review-manifest.json')
        if original.get('original_native_observed') is not True:
            raise ValueError('Original review manifest cannot be synthetic')
    channel_dir=attempt/'channels'
    channel_dir.mkdir(exist_ok=False)
    native=rows(attempt/'native-rows.jsonl')
    values={'drv.standing_or_parked':lambda row: 'parked',
            'sig.headlamp':lambda row: row['observed_beam_state'],
            'kin.velocity':lambda row: [0.0,0.0,0.0],
            'rel.occupies':lambda row: row['observed_curb_lane_id']}
    recording=[]
    for channel in construction['recording_description']['channels']:
        name=channel['name']
        if name not in values:raise ValueError('Unknown selected channel: '+name)
        path=channel_dir/(name+'.jsonl')
        with path.open('x') as stream:
            for row in native:
                stream.write(json.dumps({'time_s':row['time_s'],'value':values[name](row)})+'\n')
        recording.append({'name':name,'unit':channel['unit'],'reference':'channels/'+path.name})
    source_hashes={name:sha(attempt/name) for name in SOURCES}
    report={'format':'worker-analysis-report','case_id':case,
            'measurements':{'parked_headlamp_observation':{
                'method':'measure_parked_lamps','value':measured,'sources':source_hashes}},
            'source_complete':True,'diagnostic_fixture':context['source_kind']=='synthetic_cpu_fixture',
            'physical_or_legal_acceptance':False}
    result={'case_id':case,'measured_values':measured,
            'target_checks':[{'target':'observed selected beam state','requested':config['requested_beam_state'],
                'measured':measured['observed_beam_state'],'method':'measure_parked_lamps','tolerance':0,
                'matched':True,'physical_cause_confirmed':False,'cause_evidence':list(SOURCES)}],
            'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,
            'termination_reason':'Saved source analyzed; physical and legal review remains separate',
            'physical_failure_flags':['Actual parked activity and beam aim/intensity not physically accepted'],
            'trace_reference':'trace.jsonl','video_references':[v+'.mkv' for v in VIEWS],
            'video_frame_map_reference':'video_frames.jsonl',
            'recording_description':construction['recording_description'],
            'recording_evidence':recording,'realized_observables':{},
            'provenance_kind':context['source_kind'],'accepted':False}
    from worker_exchange.native_output import write_result
    write_result(attempt,result)
    output.write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();finalize(a.attempt,a.output)
