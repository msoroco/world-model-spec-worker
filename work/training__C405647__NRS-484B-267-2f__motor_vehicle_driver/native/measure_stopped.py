"""Join moving-then-stopped original sources; preserve NRS 484B.607 referral."""
import hashlib
import json
import math
from pathlib import Path
import subprocess

AID='training__C405647__NRS-484B-267-2f__motor_vehicle_driver'
CAMERAS=('overview','approach','reference_corner','driver_reference')
COUNT=600


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):return [json.loads(x) for x in Path(p).read_text().splitlines() if x.strip()]
def finite(x):return type(x) in (int,float) and math.isfinite(x)


def measure(root):
    root=Path(root)
    names=('video_frames.jsonl','vehicle_poses.jsonl','emergency_context.json')
    sources={n:root/n for n in names}
    if any(not p.is_file() for p in sources.values()):raise ValueError('Original frame, pose and reviewed context sources required')
    frames,poses=rows(sources[names[0]]),rows(sources[names[1]])
    c=json.loads(sources[names[2]].read_text())
    if len(frames)!=COUNT or len(poses)!=COUNT or c.get('assignment_id')!=AID:
        raise ValueError('Exact assignment and 600 source frames required')
    kind=c.get('review_kind')
    if kind not in ('synthetic_diagnostic','original_source_review'):raise ValueError('Source provenance review required')
    for k in ('reviewer','ego_driver_source','emergency_authorization_source',
              'qualifying_flash_equipment_source','flashing_light_visual_source',
              'lane_boundary_source','visibility_review_source','officer_direction_review_source'):
        if not c.get(k):raise ValueError('Missing statutory source: '+k)
    if c.get('emergency_vehicle_authorized') is not True or c.get('qualifying_flash_equipment_reviewed') is not True:
        raise ValueError('Emergency authorization or qualifying lights unproved')
    if type(c.get('officer_directed_otherwise')) is not bool:
        raise ValueError('Officer direction exception unreviewed')
    if type(c.get('ego_actor_id')) is not int or type(c.get('emergency_actor_id')) is not int or c['ego_actor_id']==c['emergency_actor_id']:
        raise ValueError('Distinct actor identities required')
    cam_hashes={}
    if kind=='original_source_review':
        for name in CAMERAS:
            p=root/(name+'.mkv')
            if not p.is_file():raise ValueError('Original camera missing: '+name)
            q=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
                              '-show_entries','stream=nb_read_frames,r_frame_rate','-of','json',str(p)],capture_output=True,text=True)
            if q.returncode:raise ValueError('Original camera decode failed: '+name)
            streams=json.loads(q.stdout).get('streams',[])
            if len(streams)!=1 or streams[0].get('nb_read_frames')!='600' or streams[0].get('r_frame_rate')!='20/1':
                raise ValueError('Original 600-frame camera source missing: '+name)
            cam_hashes[p.name]=sha(p)
        if c.get('camera_sha256')!=cam_hashes:raise ValueError('Camera source hash differs')
    prev_n=-1;prev_t=-1.0;distances=[];ego_speeds=[];em_speeds=[];light=[];derived=[]
    for i,(f,p) in enumerate(zip(frames,poses)):
        n,t=f.get('native_frame'),f.get('time_s')
        if f.get('video_frame')!=i or type(n) is not int or n<=prev_n or not finite(t) or t<=prev_t or (i and abs(t-prev_t-.05)>.005):
            raise ValueError('Original frame/time join failed')
        if p.get('video_frame')!=i or p.get('native_frame')!=n or p.get('source_kind')!=('synthetic_native_sample' if kind=='synthetic_diagnostic' else 'original_native_pose'):
            raise ValueError('Original pose provenance differs')
        e,m=p.get('ego'),p.get('emergency')
        if not isinstance(e,dict) or not isinstance(m,dict) or e.get('actor_id')!=c['ego_actor_id'] or m.get('actor_id')!=c['emergency_actor_id']:
            raise ValueError('Actor identity join failed')
        for v in (e,m):
            if any(not finite(v.get(k)) for k in ('x_m','y_m','heading_rad','velocity_x_mps','velocity_y_mps','speed_mps','half_length_m','half_width_m')):
                raise ValueError('Original vehicle pose/velocity/extent missing')
            if v['speed_mps']<0 or v['half_length_m']<=0 or v['half_width_m']<=0:
                raise ValueError('Original vehicle motion or extent invalid')
        if type(m.get('special1_light_on')) is not bool:raise ValueError('Original emergency light state missing')
        d=math.hypot(e['x_m']-m['x_m'],e['y_m']-m['y_m'])
        distances.append(d);ego_speeds.append(e['speed_mps']);em_speeds.append(m['speed_mps']);light.append(m['special1_light_on'])
        derived.append({'video_frame':i,'native_frame':n,'time_s':t,'separation_m':d,
                        'ego_x_m':e['x_m'],'ego_y_m':e['y_m'],
                        'ego_half_length_m':e['half_length_m'],
                        'ego_half_width_m':e['half_width_m'],
                        'emergency_x_m':m['x_m'],
                        'emergency_half_length_m':m['half_length_m'],
                        'ego_speed_mps':e['speed_mps'],'emergency_speed_mps':m['speed_mps'],
                        'emergency_velocity_x_mps':m['velocity_x_mps'],'heading_dot':math.cos(e['heading_rad']-m['heading_rad']),
                        'light_state_special1':m['special1_light_on']})
        prev_n,prev_t=n,t
    if frames[-1]['time_s']-frames[0]['time_s']<29.9:raise ValueError('Full 30-second observation required')
    if not distances[80]<distances[0]:raise ValueError('Initial subject approach not measured')
    if max(em_speeds[:80])>0.15 or not min(x['emergency_velocity_x_mps'] for x in derived[120:180])<-.5:
        raise ValueError('Subsequent emergency approach not measured')
    if not distances[220]<distances[120]:raise ValueError('Subsequent closing relationship not measured')
    if any(x['emergency_speed_mps']>.15 for x in derived[220:300]):
        raise ValueError('Stopped-vehicle referral not measured')
    if not all(x['heading_dot']<-.8 for x in derived[:220]):raise ValueError('Opposing distinct routes not measured')
    if set(light)!={True,False}:raise ValueError('Flashing light state changes not measured')
    suffix=c.get('case_id','').rsplit('__',1)[-1]
    if suffix != 'stopped_referral':
        raise ValueError('Exact response case missing')
    passed_frames=[x['video_frame'] for x in derived[120:] if
                   x['emergency_x_m']+x['emergency_half_length_m'] <
                   x['ego_x_m']-x['ego_half_length_m']]
    first_pass=passed_frames[0] if passed_frames else None
    if first_pass is not None:
        raise ValueError('Stopped vehicle unexpectedly passed subject')
    if (derived[100]['ego_y_m']<=derived[119]['ego_y_m'] or
        any(abs(x['ego_y_m']+2.5)>.15 or abs(x['ego_speed_mps'])>.15
            for x in derived[120:300])):
        raise ValueError('Stopped-referral right-edge holding position not measured')
    if not all(x['ego_y_m']-x['ego_half_width_m']>=-3.65 for x in derived[120:300]):
        raise ValueError('Right-edge body extends beyond authored road')
    return {'format':'source-bound-moving-then-stopped-emergency-v1','assignment_id':AID,
            'source_sha256':{**{k:sha(v) for k,v in sources.items()},**cam_hashes},
            'samples':COUNT,'initial_subject_approach_m':distances[0]-distances[80],
            'subsequent_emergency_approach_m':distances[120]-distances[220],
            'ego_speed_before_mps':sum(ego_speeds[20:80])/60,
            'ego_speed_after_mps':sum(ego_speeds[160:220])/60,
            'right_edge_stop_until_passed_observed':False,
            'stopped_referral_observed':True,
            'emergency_pass_frame':first_pass,
            'light_phase_changes':sum(a!=b for a,b in zip(light,light[1:])),
            'per_frame_geometry':derived,'subsection_1_duty_resolved':False,
            'nrs_484b_607_duty_resolved':False,'legal_result':None,
            'physical_acceptance_claimed':False}
