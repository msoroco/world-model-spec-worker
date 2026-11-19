"""Independent retained-source audit for one exact case; fixture success is not physical acceptance."""
from __future__ import annotations
import argparse,json,subprocess,hashlib
from pathlib import Path

PREFIX='heldout__C136014__NRS-484B-113-1__motor_vehicle_driver__'
SLUGS={'reverse_clear_traffic_steady','reverse_close_traffic_steady','reverse_clear_traffic_brakes', 'backing_safety_spacing_grid-0000','backing_safety_spacing_grid-0001','backing_safety_spacing_grid-0002','backing_interference_onset_grid-0000','backing_interference_onset_grid-0001','backing_interference_onset_grid-0002'}

def audit(case,attempt):
    slug=case.removeprefix(PREFIX)
    if case!=PREFIX+slug or slug not in SLUGS:raise ValueError('Wrong exact delivery case')
    attempt=Path(attempt)
    def require_source(name):
        p=attempt/name
        if not p.is_file():raise ValueError('Missing required source: '+name)
        return p
    def jsonrows(name):
        p=require_source(name);return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    history=jsonrows('backing_history.jsonl');trace=jsonrows('trace.jsonl');frames=jsonrows('video_frames.jsonl')
    if not history or len(history)!=len(trace) or len(trace)!=len(frames):raise ValueError('Original participant/time join incomplete')
    for h,t,f in zip(history,trace,frames):
        if h['frame']!=t['frame'] or h['frame']!=f['carla_frame'] or abs(h['time_s']-t['time_s'])>1e-5 or abs(h['time_s']-f['time_s'])>1e-5:
            raise ValueError('Original participant/time join incomplete')
        if not h.get('ego') or not h.get('other') or not h.get('ego_reverse_gear') or h['ego']['position_m']!=t['position_m']:
            raise ValueError('Original participant/time join incomplete')
    result=json.loads(require_source('result.json').read_text())
    if result['case_id']!=case or result.get('legal_acceptance_claimed') or result.get('physical_acceptance_claimed'):
        raise ValueError('Wrong case or unsupported acceptance claim')
    if result.get('trace_reference')!='trace.jsonl' or result.get('video_frame_map_reference')!='video_frames.jsonl':
        raise ValueError('Original trace/video map reference changed')
    names=['overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv']
    if result.get('video_references')!=names:raise ValueError('Four-view source list changed')
    decoded={}
    for name in names:
        p=require_source(name)
        probe=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=nb_read_frames','-of','default=noprint_wrappers=1:nokey=1',str(p)],capture_output=True,text=True,check=True)
        try:n=int(probe.stdout.strip())
        except ValueError:raise ValueError('Full video decode frame count unavailable: '+name)
        if n!=len(frames):raise ValueError('Full video frame count changed: '+name)
        decoded[name]=n
    return {'format':'worker-delivery-audit','case_id':case,'passed':True,'source_frames':len(frames),
            'video_frames':decoded,'source_sha256':{name:hashlib.sha256(require_source(name).read_bytes()).hexdigest() for name in ('backing_history.jsonl','trace.jsonl','video_frames.jsonl')},
            'physical_completion_check':bool(result.get('setup_confirmed') and result.get('maneuver_completed') and not result.get('physical_failure_flags')),
            'actual_pixels_check':'full codec decode and exact frame count; visual subject/body review remains required',
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}

def audit_onset_sweep(attempts):
    """Compare the three exact synthetic controls through retained joined sources."""
    expected=(40,120,80)
    if len(attempts)!=3:raise ValueError('Three exact onset attempts required')
    cases=[];fixed=None
    for index,(attempt,target) in enumerate(zip(attempts,expected)):
        case=PREFIX+f'backing_interference_onset_grid-{index:04}'
        verified=audit(case,attempt)
        attempt=Path(attempt)
        states=[json.loads(s) for s in (attempt/'backing_history.jsonl').read_text().splitlines() if s]
        frames=[json.loads(s) for s in (attempt/'video_frames.jsonl').read_text().splitlines() if s]
        if len(states)!=160 or len(frames)!=160:
            raise ValueError('Onset diagnostic lacks all 160 source-joined frames')
        constant=[(s['frame'],s['time_s'],s['ego']['position_m'],
                   s['other']['position_m'],s['ego_reverse_gear']) for s in states]
        if fixed is None:fixed=constant
        elif fixed!=constant:raise ValueError('Onset sweep changed a fixed source condition')
        speeds=[s['other']['speed_mps'] for s in states]
        decline=next((i for i in range(1,len(speeds)) if speeds[i]<speeds[i-1]-.05),None)
        if decline!=target or any(abs(speed-1.0)>1e-6 for speed in speeds[:target]) or any(abs(speed-.8)>1e-6 for speed in speeds[target:]):
            raise ValueError('Requested other-traffic onset not realized in joined source: '+case)
        result=json.loads((attempt/'result.json').read_text())
        check=next((x for x in result.get('target_checks',[]) if x.get('target')=='other_traffic_brake_start_frame'),None)
        if not check or check.get('measured')!=float(target) or check.get('matched') is not True:
            raise ValueError('Saved result onset readback differs from source: '+case)
        cases.append({'case_id':case,'requested_frame':target,'measured_frame':decline,
                      'source_frames':len(states),'four_camera_decodes':verified['video_frames'],
                      'source_sha256':verified['source_sha256']})
    return {'format':'worker-onset-sweep-source-audit','passed':True,'fixture_only':True,
            'actual_native_capture':False,'fixed_conditions_checked':True,
            'cases':cases,'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--attempt',required=True)
    a=p.parse_args();print(json.dumps(audit(a.case,a.attempt),indent=2))
if __name__=='__main__':main()
