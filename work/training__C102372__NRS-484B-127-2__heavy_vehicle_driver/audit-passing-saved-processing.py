"""Independent raw-source audit of the passing 480-frame saved fixture."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SOURCE=ROOT/'.runtime-work/c102372-passing-saved/passing_overtake-positive'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(name):return [json.loads(line) for line in (SOURCE/name).read_text().splitlines()]


def audit():
    manifest=json.loads((SOURCE/'source-manifest.json').read_text())
    if manifest['format']!='c102372-passing-source-v1':
        raise ValueError('Passing source format differs')
    for name,value in manifest['sha256'].items():
        if sha(SOURCE/name)!=value:raise ValueError('Passing source digest differs')
    config=json.loads((SOURCE/'config.json').read_text())
    context=json.loads((SOURCE/'following_context.json').read_text())
    if context.get('conditions_permit')!={
        'source':'synthetic_cpu_assertion','status':'not_physically_verified'}:
        raise ValueError('Passing authored conditions context absent')
    result=json.loads((SOURCE/'result.json').read_text())
    report=json.loads((SOURCE/'analysis-report.json').read_text())
    plan=json.loads((HERE/'case-plan.json').read_text())
    branch=plan['requirement_dispositions'][1]
    contract=json.loads((HERE/'native/measurement-contract-passing_overtake.json').read_text())
    requirement=contract['requirements'][0]
    if config['case_id'] not in branch['case_ids'] or branch['branch']!='passing while gap closes' or \
       contract['case_id']!=config['case_id'] or requirement['disposition_index']!=1 or \
       requirement['output_key']!='truck_passing_sequence' or \
       requirement['method']!='measure' or set(requirement['inputs'])!={
           'native_samples.jsonl','following_context.json','road.xodr'}:
        raise ValueError('Passing statutory/measurement binding differs')
    if config['case_id']!=result['case_id'] or result['accepted'] is not False or \
       result['provenance_kind']!='synthetic_cpu':
        raise ValueError('Passing case/scope differs')
    native,trace,evidence,join=(rows(name) for name in (
        'native_samples.jsonl','trace.jsonl','capture/evidence.jsonl','video_frames.jsonl'))
    if any(len(group)!=480 for group in (native,trace,evidence,join)):
        raise ValueError('Passing 480-frame join incomplete')
    lanes=[];offsets=[];clearance=math.inf;last_carla=-1
    for i,(n,t,e,j) in enumerate(zip(native,trace,evidence,join)):
        frame=j['carla_frame']
        if frame<=last_carla or (j['video_frame'],j['native_frame'],n['native_frame'],
           n['carla_frame'],t['frame'],e['original_frame'])!=(i,i,i,frame,frame,frame):
            raise ValueError('Passing Native/trace/evidence/video join differs')
        last_carla=frame
        if any(abs(value-i/20)>.001 for value in (j['time_s'],n['time_s'])):
            raise ValueError('Passing frame time differs')
        ego=n['ego'];lead=n['lead']
        if n['opposing_lane_actors']!=[] or ego['actor_class']!='truck_or_combination' or \
           lead['actor_class']!='truck_or_combination' or lead['lane_id']!=-1:
            raise ValueError('Passing participants or opposing source differs')
        centers=[]
        for actor in (ego,lead):
            p=actor['body_xy_m']
            if len(p)!=4 or len(actor['body_vertices_m'])!=8 or \
               max(v[1] for v in p)-min(v[1] for v in p)<2.032:
                raise ValueError('Passing truck body differs')
            center=[sum(v[k] for v in p)/4 for k in (0,1)]
            if any(abs(a-b)>.001 for a,b in zip(center,actor['center_xy_m'])):
                raise ValueError('Passing truck center differs')
            centers.append(center)
        (ex,ey),(lx,ly)=centers
        if any(abs(a-b)>.001 for a,b in zip(t['position_m'][:2],(ex,ey))) or \
           e['ego']['body_vertices_m']!=ego['body_vertices_m']:
            raise ValueError('Passing trace/evidence body differs')
        lane=1 if ey>=0 else -1
        if ego['lane_id']!=lane or e['world']['road_projection']['lane_id']!=lane:
            raise ValueError('Passing lane source differs')
        lanes.append(lane);offsets.append(ex-lx)
        value=math.hypot(max(0,abs(ex-lx)-12),max(0,abs(ey-ly)-2.6))
        clearance=min(clearance,value)
    measured=result['measured_values']['truck_passing_sequence']
    if not (measured['passing_sequence_observed'] is True and
            measured['opposing_lane_frames']==sum(lane==1 for lane in lanes) and
            math.isclose(measured['minimum_body_clearance_m'],clearance,abs_tol=1e-4) and
            math.isclose(measured['final_center_offset_m'],offsets[-1],abs_tol=1e-4)):
        raise ValueError('Passing saved measurement differs from independent raw audit')
    for name in ('overview.mkv','ego_forward.mkv','lead_gap.mkv','crest_context.mkv'):
        decoded=subprocess.run([str(ROOT/'.runtime-work/linux_arm64/ffprobe'),'-v','error',
            '-count_frames','-select_streams','v:0','-show_entries','stream=nb_read_frames',
            '-of','default=noprint_wrappers=1:nokey=1',str(SOURCE/name)],
            capture_output=True,text=True,timeout=120)
        if decoded.returncode or decoded.stdout.strip()!='480' or \
           report['video_frames'][name]!=480:
            raise ValueError('Passing video decode/proof differs')
    return {'passed':True,'frames':480,'opposing_lane_frames':sum(lane==1 for lane in lanes),
            'minimum_body_clearance_m':round(clearance,4),
            'final_center_offset_m':round(offsets[-1],4),
            'source_sha256':sha(SOURCE/'native_samples.jsonl'),
            'physical_or_accepted_claim':False}


if __name__=='__main__':print(json.dumps(audit(),sort_keys=True))
