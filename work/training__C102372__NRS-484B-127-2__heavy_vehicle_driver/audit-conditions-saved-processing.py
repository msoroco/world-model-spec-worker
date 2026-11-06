"""Independent full saved-source audit of the steady/braking controlled pair."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=ROOT/'.runtime-work/c102372-conditions-saved'
CASES=('conditions_steady','conditions_lead_brake')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(root,name):return [json.loads(line) for line in (root/name).read_text().splitlines()]


def surface_gap(row,profile):
    x0=max(x for x,_ in row['ego']['body_xy_m'])
    x1=min(x for x,_ in row['lead']['body_xy_m'])
    n=math.ceil((x1-x0)/.1);step=(x1-x0)/n;total=0
    for i in range(n):
        x=x0+(i+.5)*step
        segment=max((p for p in profile if float(p.get('s'))<=x),
                    key=lambda p:float(p.get('s')))
        u=x-float(segment.get('s'))
        slope=float(segment.get('b'))+2*float(segment.get('c'))*u+3*float(segment.get('d'))*u*u
        total+=math.hypot(1,slope)*step
    return total


def audit():
    plan=json.loads((HERE/'case-plan.json').read_text())
    checked={};pair={}
    for case in CASES:
        root=OUT/(case+'-positive')
        config=json.loads((root/'config.json').read_text())
        context=json.loads((root/'following_context.json').read_text())
        manifest=json.loads((root/'source-manifest.json').read_text())
        contract=json.loads((HERE/'native'/('measurement-contract-'+case+'.json')).read_text())
        result=json.loads((root/'result.json').read_text())
        report=json.loads((root/'analysis-report.json').read_text())
        req=contract['requirements'][0]
        if manifest['format']!='c102372-conditions-source-v1' or \
           any(sha(root/name)!=digest for name,digest in manifest['sha256'].items()) or \
           config['case_id']!=HERE.name+'__'+case or contract['case_id']!=config['case_id'] or \
           config['case_id'] not in plan['requirement_dispositions'][3]['case_ids'] or \
           req['disposition_index']!=3 or req['output_key']!='truck_conditions_event' or \
           set(req['inputs'])!=set(manifest['sha256']):
            raise ValueError('Conditions source/contract binding differs')
        target=case=='conditions_lead_brake'
        if (context['event']=='lead_brake_with_obstacle') is not target or \
           context.get('conditions_permit')!={'source':'synthetic_cpu_assertion',
                                             'status':'not_physically_verified'} or \
           result['accepted'] is not False or result['provenance_kind']!='synthetic_cpu':
            raise ValueError('Conditions context or scope differs')
        native,trace,evidence,join=(rows(root,name) for name in (
            'native_samples.jsonl','trace.jsonl','capture/evidence.jsonl','video_frames.jsonl'))
        if any(len(group)!=480 for group in (native,trace,evidence,join)):
            raise ValueError('Conditions full saved join absent')
        profile=ET.parse(root/'road.xodr').getroot().find('road').findall('elevationProfile/elevation')
        minimum=math.inf;last=-1
        for i,(n,t,e,j) in enumerate(zip(native,trace,evidence,join)):
            frame=j['carla_frame']
            if frame<=last or (j['native_frame'],j['video_frame'],n['native_frame'],
               n['carla_frame'],t['frame'],e['original_frame'])!=(i,i,i,frame,frame,frame):
                raise ValueError('Conditions Native/trace/evidence/video join differs')
            last=frame
            if abs(n['time_s']-i/20)>.001 or abs(j['time_s']-i/20)>.001:
                raise ValueError('Conditions frame time differs')
            ego=n['ego'];lead=n['lead']
            if any(actor['lane_id']!=-1 or actor['actor_class']!='truck_or_combination' or
                   len(actor['body_vertices_m'])!=8 or len(actor['body_xy_m'])!=4 or
                   max(p[1] for p in actor['body_xy_m'])-
                   min(p[1] for p in actor['body_xy_m'])<2.032 for actor in (ego,lead)):
                raise ValueError('Conditions 80-inch truck source differs')
            if (n['obstacle'] is not None) is not target or \
               e['ego']['body_vertices_m']!=ego['body_vertices_m'] or \
               any(abs(a-b)>.001 for a,b in zip(t['position_m'][:2],ego['center_xy_m'])):
                raise ValueError('Conditions obstacle or trace/evidence differs')
            minimum=min(minimum,surface_gap(n,profile))
        value=result['measured_values']['truck_conditions_event']
        if value['lead_braking_gap_compression_observed'] is not target or \
           abs(value['minimum_surface_gap_m']-minimum)>.002 or \
           result['target_checks'][0]['matched'] is not True:
            raise ValueError('Conditions measured event/road arc differs')
        for name in ('overview.mkv','ego_forward.mkv','lead_gap.mkv','crest_context.mkv'):
            decoded=subprocess.run([str(ROOT/'.runtime-work/linux_arm64/ffprobe'),'-v','error',
                '-count_frames','-select_streams','v:0','-show_entries','stream=nb_read_frames',
                '-of','default=noprint_wrappers=1:nokey=1',str(root/name)],
                capture_output=True,text=True,timeout=120)
            if decoded.returncode or decoded.stdout.strip()!='480' or report['video_frames'][name]!=480:
                raise ValueError('Conditions video decode differs')
        pair[case]=native
        checked[case]={'event':target,'minimum_surface_gap_m':round(minimum,4),
                       'source_sha256':sha(root/'native_samples.jsonl')}
    steady=pair[CASES[0]];brake=pair[CASES[1]]
    for i in range(161):
        for role in ('ego','lead'):
            a=steady[i][role]['body_xy_m'];b=brake[i][role]['body_xy_m']
            if any(abs(x-y)>1e-6 for p,q in zip(a,b) for x,y in zip(p,q)) or \
               abs(steady[i][role]['speed_mps']-brake[i][role]['speed_mps'])>1e-6:
                raise ValueError('Conditions pre-event controlled trace differs')
    if not checked[CASES[0]]['minimum_surface_gap_m']>152.4 or \
       not checked[CASES[1]]['minimum_surface_gap_m']<152.4 or \
       brake[160]['lead']['speed_mps']!=8 or brake[200]['lead']['speed_mps']!=0 or \
       brake[180]['ego']['speed_mps']!=8 or brake[260]['ego']['speed_mps']!=0:
        raise ValueError('Conditions controlled braking event differs')
    return {'passed':True,'frames_per_case':480,'pre_event_fixed_frames':161,
            'cases':checked,'physical_or_accepted_claim':False}


if __name__=='__main__':print(json.dumps(audit(),sort_keys=True))
