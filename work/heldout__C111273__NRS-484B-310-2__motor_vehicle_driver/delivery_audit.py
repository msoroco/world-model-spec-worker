"""Independent retained-source and full camera decode audit for flashing yellow."""
import argparse,hashlib,json
from pathlib import Path

CAMERAS=('overview','approach','reference_corner','driver_reference')
REQUIRED=('signal_context.json','signal_state.jsonl','participant_state.jsonl',
          'video_frames.jsonl','trace.jsonl')
def _hash(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def _rows(path):return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]

def audit_attempt(attempt,analysis,case,*,decoder=None,receipt_dir=None):
    root=Path(attempt)
    report=json.loads(Path(analysis).read_text()) if not isinstance(analysis,dict) else analysis
    if report.get('case_id')!=case:raise ValueError('Analysis selects another exact case')
    for name in (*REQUIRED,'config.json'):
        if not (root/name).is_file():raise ValueError('Missing audited original source: '+name)
    config=json.loads((root/'config.json').read_text())
    if config.get('selected_case_id')!=case:raise ValueError('Native config selects another exact case')
    context=json.loads((root/'signal_context.json').read_text())
    if not context.get('official_control_source') or not context.get('opendrive_id'):
        raise ValueError('Original official-control premise or governed lane absent')
    item=report['measurements']['flashing_yellow']
    hashes=item.get('sources',{})
    if set(hashes)!=set(REQUIRED):raise ValueError('Analysis source inventory incomplete')
    if any(_hash(root/name)!=digest for name,digest in hashes.items()):
        raise ValueError('Analysis source hash differs from retained acquisition')
    frames=_rows(root/'video_frames.jsonl');trace=_rows(root/'trace.jsonl')
    signals=_rows(root/'signal_state.jsonl');parties=_rows(root/'participant_state.jsonl')
    if not frames or not len(frames)==len(trace)==len(signals)==len(parties):
        raise ValueError('Original signal source frame count differs')
    light_id=ego_id=None;states=[];crossing=None
    for i,(fm,motion,light,party) in enumerate(zip(frames,trace,signals,parties)):
        identity=(fm.get('carla_frame'),fm.get('time_s'))
        if fm.get('video_frame')!=i or any((row.get('frame'),row.get('time_s'))!=identity
             for row in (motion,light,party)):
            raise ValueError('Original signal source frame identity differs')
        if light_id is None:light_id=light.get('light_actor_id')
        if light.get('light_actor_id')!=light_id or light.get('opendrive_id')!=context['opendrive_id']:
            raise ValueError('Original signal head identity differs')
        state=light.get('native_light_state','')
        if isinstance(state,str):state=state.removeprefix('TrafficLightState.')
        if state not in ('Yellow','Off') or light.get('yellow_commanded')!=(state=='Yellow'):
            raise ValueError('Original Native lamp command/readback differs')
        states.append(state=='Yellow')
        ego=party.get('ego')
        if not isinstance(ego,dict) or type(ego.get('actor_id')) is not int:
            raise ValueError('Missing original subject participant')
        if ego_id is None:ego_id=ego['actor_id']
        if ego['actor_id']!=ego_id:raise ValueError('Original subject identity changed')
        has_crossing=party.get('crossing') is not None
        if crossing is None:crossing=has_crossing
        if has_crossing!=crossing:raise ValueError('Crossing participant continuity differs')
    transitions=sum(a!=b for a,b in zip(states,states[1:]))
    value=item['value']
    if transitions!=value.get('native_transitions') or transitions<1 or crossing!=value.get('crossing_present'):
        raise ValueError('Analysis signal measurement differs from independent original-source recomputation')
    if value.get('lens_pixel_visibility')!='unverified' or value.get('legal_caution_judgment')!='unresolved':
        raise ValueError('Diagnostic analysis asserted unreviewed lens pixels or caution')
    if decoder is None:
        from worker_exchange.media import audit as decoder
    if receipt_dir is not None:Path(receipt_dir).mkdir(parents=True,exist_ok=False)
    cameras={}
    for name in CAMERAS:
        path=root/(name+'.mkv')
        if not path.is_file():raise ValueError('Missing named original camera: '+name)
        receipt=None if receipt_dir is None else Path(receipt_dir)/(name+'-decode.json')
        observed=decoder(path,len(frames),mapping_sha256=_hash(root/'video_frames.jsonl'),receipt=receipt)
        if observed.get('frames')!=len(frames):raise ValueError('Camera full-decode frame count differs')
        cameras[name]={'source_sha256':_hash(path),'decode':observed}
    return {'format':'worker-signal-source-audit','case_id':case,'frame_count':len(frames),
      'source_hashes':hashes,'camera_decodes':cameras,
      'checks':{'native_source':True,'all_participants':True,'time_join':True,
        'full_video_decode':True,'actual_pixels':'source_frames_decoded_only',
        'physical_completion':'unverified'},
      'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',required=True)
    parser.add_argument('--attempt',required=True);parser.add_argument('--analysis',required=True)
    parser.add_argument('--output',required=True);args=parser.parse_args()
    out=Path(args.output)
    if out.exists():raise ValueError('Retain previous audit receipt')
    receipt=audit_attempt(args.attempt,args.analysis,args.case,
       receipt_dir=out.parent/(out.stem+'-decodes'))
    out.write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':main()
