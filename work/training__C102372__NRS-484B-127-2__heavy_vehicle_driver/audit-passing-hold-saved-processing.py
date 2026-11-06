"""Independent raw 480-frame audit of the no-passing saved control."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SOURCE=ROOT/'.runtime-work/c102372-passing-hold-saved/passing_hold-positive'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(name):return [json.loads(line) for line in (SOURCE/name).read_text().splitlines()]


def audit():
    manifest=json.loads((SOURCE/'source-manifest.json').read_text())
    if manifest['format']!='c102372-passing-source-v1':
        raise ValueError('Hold source format differs')
    for name,value in manifest['sha256'].items():
        if sha(SOURCE/name)!=value:raise ValueError('Hold source digest differs')
    config=json.loads((SOURCE/'config.json').read_text())
    context=json.loads((SOURCE/'following_context.json').read_text())
    result=json.loads((SOURCE/'result.json').read_text())
    report=json.loads((SOURCE/'analysis-report.json').read_text())
    contract=json.loads((HERE/'native/measurement-contract-passing_hold.json').read_text())
    plan=json.loads((HERE/'case-plan.json').read_text())
    req=contract['requirements'][0]
    if config['case_id'] not in plan['requirement_dispositions'][1]['case_ids'] or \
       contract['case_id']!=config['case_id'] or req['disposition_index']!=1 or \
       req['output_key']!='truck_passing_sequence' or req['method']!='measure' or \
       set(req['inputs'])!=set(manifest['sha256']):
        raise ValueError('Hold statutory or contract binding differs')
    if context['passing_attempt'] is not False or \
       context.get('conditions_permit')!={'source':'synthetic_cpu_assertion',
                                         'status':'not_physically_verified'} or \
       result['accepted'] is not False or result['provenance_kind']!='synthetic_cpu':
        raise ValueError('Hold source/scope differs')
    native,trace,evidence,join=(rows(name) for name in (
        'native_samples.jsonl','trace.jsonl','capture/evidence.jsonl','video_frames.jsonl'))
    if any(len(group)!=480 for group in (native,trace,evidence,join)):
        raise ValueError('Hold frame join incomplete')
    clearance=math.inf;last_frame=-1
    for i,(n,t,e,j) in enumerate(zip(native,trace,evidence,join)):
        frame=j['carla_frame']
        if frame<=last_frame or (j['native_frame'],j['video_frame'],n['native_frame'],
           n['carla_frame'],t['frame'],e['original_frame'])!=(i,i,i,frame,frame,frame):
            raise ValueError('Hold Native/Core/video frame join differs')
        last_frame=frame
        if abs(n['time_s']-i/20)>.001 or abs(j['time_s']-i/20)>.001:
            raise ValueError('Hold time join differs')
        ego=n['ego'];lead=n['lead']
        if n['opposing_lane_actors']!=[] or ego['lane_id']!=-1 or lead['lane_id']!=-1:
            raise ValueError('Hold truck departed lane or opposing source differs')
        centers=[]
        for actor in (ego,lead):
            points=actor['body_xy_m']
            if len(points)!=4 or len(actor['body_vertices_m'])!=8 or \
               max(p[1] for p in points)-min(p[1] for p in points)<2.032:
                raise ValueError('Hold 80-inch truck body differs')
            center=[sum(p[k] for p in points)/4 for k in (0,1)]
            if any(abs(a-b)>.001 for a,b in zip(center,actor['center_xy_m'])):
                raise ValueError('Hold source body center differs')
            centers.append(center)
        (ex,ey),(lx,ly)=centers
        if ex>=lx-12 or abs(ey+2)>.01 or abs(ly+2)>.01 or \
           any(abs(a-b)>.001 for a,b in zip((ex,ey),t['position_m'][:2])) or \
           e['ego']['body_vertices_m']!=ego['body_vertices_m']:
            raise ValueError('Hold ordering, center, or evidence differs')
        clearance=min(clearance,math.hypot(max(0,abs(ex-lx)-12),max(0,abs(ey-ly)-2.6)))
    measured=result['measured_values']['truck_passing_sequence']
    if measured['passing_sequence_observed'] is not False or \
       measured['opposing_lane_frames']!=0 or \
       not math.isclose(measured['minimum_body_clearance_m'],clearance,abs_tol=1e-4) or \
       result['target_checks'][0]['matched'] is not True:
        raise ValueError('Hold saved measurement differs from raw source')
    passing=ROOT/'.runtime-work/c102372-passing-saved/passing_overtake-positive'
    other=[json.loads(line) for line in (passing/'native_samples.jsonl').read_text().splitlines()]
    other_result=json.loads((passing/'result.json').read_text())
    if len(other)!=480 or other_result['measured_values']['truck_passing_sequence'][
            'passing_sequence_observed'] is not True:
        raise ValueError('Controlled passing partner absent')
    if native[0]['ego']['center_xy_m']!=other[0]['ego']['center_xy_m']:
        raise ValueError('Hold/pass initial ego state differs')
    for held,passed in zip(native,other):
        if any(abs(a-b)>1e-3 for a,b in zip(
               held['lead']['center_xy_m'],passed['lead']['center_xy_m'])) or \
           held['lead']['lane_id']!=passed['lead']['lane_id']:
            raise ValueError('Hold/pass lead control differs')
    if native[200]['ego']['lane_id']==other[200]['ego']['lane_id']:
        raise ValueError('Hold/pass intervention did not change lane sequence')
    for name in ('overview.mkv','ego_forward.mkv','lead_gap.mkv','crest_context.mkv'):
        decoded=subprocess.run([str(ROOT/'.runtime-work/linux_arm64/ffprobe'),'-v','error',
            '-count_frames','-select_streams','v:0','-show_entries','stream=nb_read_frames',
            '-of','default=noprint_wrappers=1:nokey=1',str(SOURCE/name)],
            capture_output=True,text=True,timeout=120)
        if decoded.returncode or decoded.stdout.strip()!='480' or report['video_frames'][name]!=480:
            raise ValueError('Hold source video decode differs')
    return {'passed':True,'frames':480,'minimum_body_clearance_m':round(clearance,4),
            'passing_sequence_observed':False,'source_sha256':sha(SOURCE/'native_samples.jsonl'),
            'controlled_lead_frames':480,'physical_or_accepted_claim':False}


if __name__=='__main__':print(json.dumps(audit(),sort_keys=True))
