"""Audit the controlled entry-centerline contrast from original diagnostic sources."""
import argparse,hashlib,json
from pathlib import Path
from turn_position_finalizer import analyze_attempt
from body_position import measure_frame

CAMERAS=('overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv')
FIXED=('route_survey_original.json','video_frames.jsonl')+CAMERAS

def require(ok,message):
    if not ok:raise ValueError(message)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def lines(path):return [json.loads(line) for line in Path(path).read_text().splitlines() if line]
def audit(reference,entry,negative_source=False):
    roots=[Path(reference),Path(entry)]
    configs=[json.loads((root/'config.json').read_text()) for root in roots]
    require(configs[0]['selected_case_id'].endswith('__centerline_approach_left_curb_departure') and configs[1]['selected_case_id'].endswith('__entry_body_straddles_centerline'),'Wrong entry comparison case identities')
    for key in ('law_id','cell_id','actor','rate_hz','duration_s','frames','cameras'):
        require(configs[0][key]==configs[1][key],'Entry comparison changed fixed configuration: '+key)
    e0,e1=(c['engineering'] for c in configs)
    require(e0['departure_target_offset_m']==e1['departure_target_offset_m']==1.2 and e0['approach_target_offset_m']==1.2 and e1['approach_target_offset_m']==0.2,'Entry comparison changed wrong engineering target')
    fixed={name:[sha(root/name) for root in roots] for name in FIXED}
    if negative_source:fixed['route_survey_original.json'][1]='0'*64
    for name,values in fixed.items():
        require(values[0]==values[1],'Entry comparison changed fixed original source: '+name)
    reports=[analyze_attempt(root,write_channels=False) for root in roots]
    bodies=[lines(root/'body_corners_original.jsonl') for root in roots]
    traces=[lines(root/'trace.jsonl') for root in roots]
    survey=json.loads((roots[0]/'route_survey_original.json').read_text())
    require(len(bodies[0])==len(bodies[1])>0,'Entry comparison frame count differs')
    for i in (0,1):
        require(len(traces[i])==len(bodies[i]),'Entry trace/body count differs')
        for body,motion in zip(bodies[i],traces[i]):
            require((body['frame'],body['time_s'])==(motion['frame'],motion['time_s']),'Entry trace/body frame join differs')
            center=[sum(v[axis] for v in body['body_corners_xy_m'])/4 for axis in (0,1)]
            require(all(abs(center[axis]-motion['position_m'][axis])<.05 for axis in (0,1)),'Entry body/trace pose differs')
    for phase in ('approach','entry','departure'):
        left=[x['body_corners_xy_m'] for x in bodies[0] if x['phase']==phase]
        right=[x['body_corners_xy_m'] for x in bodies[1] if x['phase']==phase]
        require((left!=right)==(phase!='departure'),'Entry comparison changed wrong body phase: '+phase)
    reference_entry=[measure_frame(x,survey) for x in bodies[0] if x['phase']=='entry']
    varied_entry=[measure_frame(x,survey) for x in bodies[1] if x['phase']=='entry']
    require(all(x['all_corners_right_of_approach_centerline'] for x in reference_entry),'Reference body not right of centerline')
    require(all(not x['all_corners_right_of_approach_centerline'] and min(x['approach_centerline_signed_corner_offsets_m'])<0<max(x['approach_centerline_signed_corner_offsets_m']) for x in varied_entry),'Variant body does not straddle original entry centerline')
    values=[{k:v['value'] for k,v in report['measurements'].items()} for report in reports]
    require(values[0]['approach_body_to_centerline']!=values[1]['approach_body_to_centerline'] and values[0]['departure_body_to_left_curb']==values[1]['departure_body_to_left_curb'],'Entry comparison lacks isolated saved measurement difference')
    return {'format':'worker-turn-entry-comparison-audit','case_ids':[c['selected_case_id'] for c in configs],'original_entry_frames':len(reference_entry),'fixed_original_source_sha256':{k:v[0] for k,v in fixed.items()},'reference_all_right':True,'variant_original_body_straddles':True,'saved_measurement_difference_isolated':True,'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--reference',required=True);parser.add_argument('--entry',required=True);parser.add_argument('--negative-source',action='store_true');args=parser.parse_args();print(json.dumps(audit(args.reference,args.entry,args.negative_source),indent=2))
