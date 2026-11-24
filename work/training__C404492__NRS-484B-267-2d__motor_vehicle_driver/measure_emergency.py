"""Measure original same-direction/abreast/overtake geometry without legal cutoffs."""
import hashlib
import json
import math
import subprocess
from pathlib import Path

AID='training__C404492__NRS-484B-267-2d__motor_vehicle_driver'
COUNT=600
CAMERAS=('overview','approach','side','rear')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def finite(x):return type(x) in (int,float) and math.isfinite(x)


def measure(root):
    root=Path(root)
    sources={name:root/name for name in ('video_frames.jsonl','vehicle_poses.jsonl','trace.jsonl','emergency_context.json')}
    if any(not p.is_file() for p in sources.values()):raise ValueError('Original frame, poses and reviewed context required')
    frames,poses,traces=(rows(sources[name]) for name in ('video_frames.jsonl','vehicle_poses.jsonl','trace.jsonl'))
    ctx=json.loads(sources['emergency_context.json'].read_text())
    if len(frames)!=COUNT or len(poses)!=COUNT or len(traces)!=COUNT or ctx.get('assignment_id')!=AID:
        raise ValueError('Exact assignment and 600 source frames required')
    kind=ctx.get('review_kind')
    if kind not in ('synthetic_diagnostic','original_source_review'):
        raise ValueError('Source provenance not reviewed')
    for key in ('reviewer','ego_driver_source','ego_vehicle_source','emergency_authorization_source',
                'qualifying_flash_equipment_source','flashing_light_visual_source',
                'lane_boundary_source','officer_direction_review_source'):
        if not ctx.get(key):raise ValueError('Missing statutory context source: '+key)
    if ctx.get('emergency_vehicle_authorized') is not True or ctx.get('qualifying_flash_equipment_reviewed') is not True:
        raise ValueError('Authorization or qualifying flashing equipment unproved')
    if type(ctx.get('officer_directed_otherwise')) is not bool:
        raise ValueError('Officer direction exception not reviewed')
    if type(ctx.get('ego_actor_id')) is not int or type(ctx.get('emergency_actor_id')) is not int or ctx['ego_actor_id']==ctx['emergency_actor_id']:
        raise ValueError('Separate subject and emergency actor identities required')
    cam_hashes={}
    if kind=='original_source_review':
        for name in CAMERAS:
            path=root/(name+'.mkv')
            if not path.is_file():raise ValueError('Original camera missing: '+name)
            probe=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
                '-show_entries','stream=nb_read_frames,r_frame_rate','-of','json',str(path)],capture_output=True,text=True)
            if probe.returncode:raise ValueError('Original camera decode failed: '+name)
            streams=json.loads(probe.stdout).get('streams',[])
            if len(streams)!=1 or streams[0].get('nb_read_frames')!=str(COUNT) or streams[0].get('r_frame_rate')!='20/1':
                raise ValueError('Original camera 600-frame/20-Hz source absent')
            cam_hashes[path.name]=sha(path)
        if ctx.get('camera_sha256')!=cam_hashes:
            raise ValueError('Reviewed flashing-light/camera source hash differs')
    prev_n,prev_t=-1,-1.0
    derived=[]
    light_phases=[]
    for i,(f,p,trace) in enumerate(zip(frames,poses,traces)):
        n,t=f.get('native_frame'),f.get('time_s')
        if f.get('video_frame')!=i or type(n) is not int or n<=prev_n or not finite(t) or t<=prev_t or (i and abs(t-prev_t-.05)>.005):
            raise ValueError('Original frame/time join failed')
        if p.get('video_frame')!=i or p.get('native_frame')!=n or p.get('source_kind')!=('synthetic_native_sample' if kind=='synthetic_diagnostic' else 'original_native_pose'):
            raise ValueError('Original pose provenance differs')
        if f.get('camera_native_frames')!={name:n for name in CAMERAS}:
            raise ValueError('Four original camera frames do not join')
        ego,em=p.get('ego'),p.get('emergency')
        if not isinstance(ego,dict) or not isinstance(em,dict) or ego.get('actor_id')!=ctx['ego_actor_id'] or em.get('actor_id')!=ctx['emergency_actor_id']:
            raise ValueError('Ego and emergency actor identity join failed')
        for v in (ego,em):
            if any(not finite(v.get(k)) for k in ('x_m','y_m','heading_rad','speed_mps','half_length_m','half_width_m')) or v['half_length_m']<=0 or v['half_width_m']<=0 or v['speed_mps']<0:
                raise ValueError('Original vehicle pose, extent or motion absent')
        position=trace.get('position_m')
        if (trace.get('frame')!=n or not finite(trace.get('time_s')) or abs(trace['time_s']-t)>1e-5
                or not isinstance(position,list) or len(position)!=3 or any(not finite(x) for x in position)
                or abs(position[0]-ego['x_m'])>1e-4 or abs(position[1]-ego['y_m'])>1e-4
                or not finite(trace.get('heading_deg'))
                or abs(trace['heading_deg']*math.pi/180-ego['heading_rad'])>1e-4
                or not finite(trace.get('speed_mps')) or abs(trace['speed_mps']-ego['speed_mps'])>1e-4):
            raise ValueError('Original ego trace and pose do not join')
        if type(em.get('flashing_light_phase_on')) is not bool:
            raise ValueError('Original flashing-light phase missing')
        light_phases.append(em['flashing_light_phase_on'])
        if em['speed_mps']<=0:
            raise ValueError('Selected moving emergency branch not observed')
        dx,dy=ego['x_m']-em['x_m'],ego['y_m']-em['y_m']
        dot=math.cos(ego['heading_rad']-em['heading_rad'])
        if dot<=0.5 or abs(dy)<=ego['half_width_m']+em['half_width_m']:
            raise ValueError('Selected same-direction adjacent-lane geometry absent')
        a0,a1=ego['x_m']-ego['half_length_m'],ego['x_m']+ego['half_length_m']
        b0,b1=em['x_m']-em['half_length_m'],em['x_m']+em['half_length_m']
        derived.append({'video_frame':i,'native_frame':n,'time_s':t,
            'longitudinal_intervals_m':[[a0,a1],[b0,b1]],
            'longitudinal_overlap_length_m':max(0,min(a1,b1)-max(a0,b0)),
            'ego_minus_emergency_longitudinal_m':dx,'lateral_separation_m':dy,
            'heading_dot':dot,'ego_speed_mps':ego['speed_mps'],
            'emergency_speed_mps':em['speed_mps']})
        prev_n,prev_t=n,t
    if frames[-1]['time_s']-frames[0]['time_s']<29.9:
        raise ValueError('Full 30-second observation required')
    if set(light_phases)!={False,True} or not any(a!=b for a,b in zip(light_phases,light_phases[1:])):
        raise ValueError('Observed flashing-light phase changes missing')
    crossings=sum(a['ego_minus_emergency_longitudinal_m']<0<=b['ego_minus_emergency_longitudinal_m'] for a,b in zip(derived,derived[1:]))
    return {'format':'source-bound-emergency-abreast-v1','assignment_id':AID,
        'source_sha256':{**{k:sha(v) for k,v in sources.items()},**cam_hashes},
        'samples':COUNT,'per_frame_geometry':derived,'relative_order_crossings':crossings,
        'observed_light_phase_changes':sum(a!=b for a,b in zip(light_phases,light_phases[1:])),
        'same_direction_cutoff':None,'abreast_cutoff':None,'legal_result':None,
        'officer_directed_otherwise':ctx['officer_directed_otherwise'],
        'physical_acceptance_claimed':False}
