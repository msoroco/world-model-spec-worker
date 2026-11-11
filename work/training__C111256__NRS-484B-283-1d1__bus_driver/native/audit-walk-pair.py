"""Independent synthetic pair audit of original-shaped Walk and actor rows."""
import copy
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
FIX=ROOT/'.runtime-work'/'c111256-walk-measurement'


def require(ok,message):
    if not ok:raise ValueError(message)


def load(suffix):
    folder=FIX/suffix
    files={name:(folder/name).read_bytes() for name in
           ('native_samples.jsonl','video_frames.jsonl','road_geometry.json')}
    return ([json.loads(line) for line in files['native_samples.jsonl'].splitlines()],
            [json.loads(line) for line in files['video_frames.jsonl'].splitlines()],
            json.loads(files['road_geometry.json']),
            {name:hashlib.sha256(data).hexdigest() for name,data in files.items()})


def audit(ref,contrast):
    r,rm,rg,rh=ref;c,cm,cg,ch=contrast
    require(len(r)==len(c)==len(rm)==len(cm)==480 and rg==cg and
            rh['road_geometry.json']==ch['road_geometry.json'],
            'Controlled Walk source lengths or geometry differ')
    changes=[];ref_conflict=[];contrast_conflict=[];ped_active=0
    for i,(a,b,ma,mb) in enumerate(zip(r,c,rm,cm)):
        require(ma==mb and a['native_frame']==b['native_frame']==ma['native_frame'] and
                a['time_s']==b['time_s']==ma['time_s'] and
                a['walk_signal_actor_id']==b['walk_signal_actor_id']==620 and
                a['pedestrian_actor_id']==b['pedestrian_actor_id']==720 and
                a['bus_actor_id']==b['bus_actor_id']==820 and
                a['walk_signal_display_observed']==b['walk_signal_display_observed']=='Walk' and
                a['pedestrian_facing_signal']==b['pedestrian_facing_signal'] is True and
                a['pedestrian_body_xy_m']==b['pedestrian_body_xy_m'] and
                a['speed_provenance']==b['speed_provenance']=='synthetic_native_sample',
                'Fixed signal, pedestrian, identities, provenance or frame map changed')
        ped=a['pedestrian_body_xy_m']
        ped_here=(min(p[0] for p in ped)<=3.5 and max(p[0] for p in ped)>=0 and
                  min(p[1] for p in ped)<=-10 and max(p[1] for p in ped)>=-12)
        ped_active+=int(ped_here)
        if a['bus_body_xy_m']!=b['bus_body_xy_m']:
            changes.append(i)
        for row,bucket in ((a,ref_conflict),(b,contrast_conflict)):
            bus=row['bus_body_xy_m']
            bus_here=(min(p[0] for p in bus)<=3.5 and max(p[0] for p in bus)>=0 and
                      min(p[1] for p in bus)<=-10 and max(p[1] for p in bus)>=-12)
            if bus_here and ped_here:bucket.append(i)
    require(ped_active==19 and not ref_conflict and len(contrast_conflict)==19 and
            changes==list(range(130,200)),
            'Controlled Walk crossing contrast differs')
    return {'raw_pair_frame_joins':480,'directed_pedestrian_frames':ped_active,
            'reference_simultaneous_conflict_frames':len(ref_conflict),
            'contrast_simultaneous_conflict_frames':len(contrast_conflict),
            'changed_bus_body_frames':len(changes),'source_sha256':{'reference':rh,'contrast':ch},
            'synthetic_only':True,'legal_verdict_claimed':False}


if __name__=='__main__':
    reference=load('reference');contrast=load('contrast')
    value=audit(reference,contrast)
    rejected=0
    for damage in ('wrong_signal','changed_pedestrian','stale_map'):
        modified=copy.deepcopy(contrast)
        if damage=='wrong_signal':modified[0][135]['walk_signal_display_observed']='Wait'
        elif damage=='changed_pedestrian':modified[0][135]['pedestrian_body_xy_m'][0][0]=-4
        else:modified[1][200]['native_frame']=999
        try:audit(reference,modified)
        except ValueError:rejected+=1
        else:raise ValueError('Damaged controlled pair accepted')
    value['isolated_negative_rejections']=rejected
    print(json.dumps(value,sort_keys=True))
