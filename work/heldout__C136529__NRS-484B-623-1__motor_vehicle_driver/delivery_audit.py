"""Independent original-source audit for the narrow-road slow-speed package.

CPU fixtures prove rejection and decode mechanics only. They cannot establish
real participant visibility, traffic impedance, or legal compliance.
"""
import argparse
from hashlib import sha256
import json
from math import hypot
from pathlib import Path

CAMERAS=('overview','approach','reference_corner','driver_reference')
REQUIRED=('video_frames.jsonl','trace.jsonl','participant_state.jsonl',
          'prop_state.jsonl','slow_context.json')

def _hash(path):return sha256(Path(path).read_bytes()).hexdigest()
def _rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]

def audit_attempt(attempt,analysis,case,*,decoder=None,receipt_dir=None):
    root=Path(attempt)
    report=json.loads(Path(analysis).read_text()) if not isinstance(analysis,dict) else analysis
    if report.get('case_id')!=case:raise ValueError('Analysis selects another exact case')
    for name in (*REQUIRED,'config.json'):
        if not (root/name).is_file():raise ValueError('Missing audited original source: '+name)
    config=json.loads((root/'config.json').read_text())
    if config.get('selected_case_id')!=case:raise ValueError('Native config selects another exact case')
    source_hashes=report['measurements']['slow_speed_observation']['sources']
    if set(source_hashes)!=set(REQUIRED):raise ValueError('Analysis source inventory incomplete')
    if any(_hash(root/name)!=expected for name,expected in source_hashes.items()):
        raise ValueError('Analysis source hash differs from retained acquisition')
    frame_map=_rows(root/'video_frames.jsonl');trace=_rows(root/'trace.jsonl')
    actors=_rows(root/'participant_state.jsonl');props=_rows(root/'prop_state.jsonl')
    if not frame_map or not len(frame_map)==len(trace)==len(actors)==len(props):
        raise ValueError('Original source frame count differs')
    gaps=[];ego_speeds=[];follower_speeds=[]
    for i,(mapping,t,a,p) in enumerate(zip(frame_map,trace,actors,props)):
        ident=(mapping.get('carla_frame'),mapping.get('time_s'))
        if mapping.get('video_frame')!=i or any((r.get('frame'),r.get('time_s'))!=ident for r in (t,a,p)):
            raise ValueError('Original source frame identity differs')
        if any(a.get(role+'_valid') is not True for role in ('ego','follower','opposing')):
            raise ValueError('Missing original participant body history')
        gaps.append(hypot(a['ego_xy'][0]-a['follower_xy'][0],a['ego_xy'][1]-a['follower_xy'][1]))
        ego_speeds.append(a['ego_speed_mps']);follower_speeds.append(a['follower_speed_mps'])
    value=report['measurements']['slow_speed_observation']['value']
    if (abs(min(gaps)-value['minimum_follower_gap_m'])>1e-6
            or abs(sum(ego_speeds)/len(ego_speeds)-value['mean_ego_speed_mps'])>1e-6
            or abs(sum(follower_speeds)/len(follower_speeds)-value['mean_follower_speed_mps'])>1e-6):
        raise ValueError('Analysis measurement differs from independent original-source recomputation')
    context=json.loads((root/'slow_context.json').read_text());branch=context['case_branch']
    if branch=='slow_for_obstruction' and not all(p.get('obstruction_present') and
            len((p.get('obstruction_geometry') or {}).get('vertices_xyz',[]))>=4 for p in props):
        raise ValueError('Physical obstruction geometry missing from original source')
    if branch=='slow_under_control' and (not context.get('regulatory_source') or
            not all(p.get('control_present') and
                    len((p.get('control_geometry') or {}).get('vertices_xyz',[]))>=4 for p in props)):
        raise ValueError('Physical control geometry or regulatory source missing')
    if decoder is None:
        from worker_exchange.media import audit as decoder
    receipts={}
    if receipt_dir is not None:Path(receipt_dir).mkdir(parents=True,exist_ok=False)
    for camera in CAMERAS:
        path=root/(camera+'.mkv')
        if not path.is_file():raise ValueError('Missing named original camera: '+camera)
        receipt=None if receipt_dir is None else Path(receipt_dir)/(camera+'-decode.json')
        observed=decoder(path,len(frame_map),mapping_sha256=_hash(root/'video_frames.jsonl'),receipt=receipt)
        if observed.get('frames')!=len(frame_map):raise ValueError('Camera full-decode frame count differs')
        receipts[camera]={'source_sha256':_hash(path),'decode':observed}
    return {'format':'worker-slow-source-audit','case_id':case,'frame_count':len(frame_map),
            'source_hashes':source_hashes,'camera_decodes':receipts,
            'checks':{'native_source':True,'all_participants':True,'time_join':True,
                      'full_video_decode':True,'actual_pixels':'source_frames_decoded_only',
                      'physical_completion':'unverified'},
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',required=True)
    parser.add_argument('--attempt',required=True);parser.add_argument('--analysis',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args();out=Path(args.output)
    if out.exists():raise ValueError('Retain previous audit receipt')
    report=audit_attempt(args.attempt,args.analysis,args.case,receipt_dir=out.parent/(out.stem+'-decodes'))
    out.write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
