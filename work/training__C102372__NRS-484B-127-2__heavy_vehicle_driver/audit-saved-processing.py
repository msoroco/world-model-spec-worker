"""Independent readback of two saved truck-gap positives and absent-source negatives."""
import hashlib
import json
import os
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SOURCE=ROOT/'.runtime-work/c102372-saved-processing'
sys.path.insert(0,str(HERE/'native'))
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from measure_gap import measure
from finalize import finalize,frames
from worker_exchange.measurement_contract import verify_report


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):return json.loads(path.read_text())


def rows(path):return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit():
    os.environ['PATH']=str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+os.environ.get('PATH','')
    source={}
    for case in ('probe_1','probe_2'):
        root=SOURCE/(case+'-positive')
        data=read(root/'result.json');report=read(root/'analysis-report.json')
        contract=read(HERE/'native'/('measurement-contract-'+case+'.json'))
        measured=measure(root)
        if data['accepted'] or data['legal_verdict_claimed'] or data['case_id']!=contract['case_id']:
            raise ValueError('Saved result claims acceptance or wrong case')
        if data['measured_values']['truck_following_gap']!=measured:
            raise ValueError('Saved truck gap differs from independent source recomputation')
        verify_report(contract,report,root)
        native=rows(root/'native_samples.jsonl');mapping=rows(root/'video_frames.jsonl')
        if len(native)!=480 or len(mapping)!=480:
            raise ValueError('Saved frame count differs')
        if any(row['native_frame']!=i or mapping[i]['carla_frame']!=row['carla_frame']
               for i,row in enumerate(native)):
            raise ValueError('Saved original truck frame mapping differs')
        if any(frames(root/name)!=480 for name in ('overview.mkv','ego_forward.mkv',
                                                  'lead_gap.mkv','crest_context.mkv')):
            raise ValueError('Original video frame decode differs')
        negative=SOURCE/(case+'-negative')
        try:finalize(negative,negative/'analysis-report.json')
        except ValueError as exc:
            if 'Missing required source: native_samples.jsonl' not in str(exc):raise
        else:raise ValueError('Removed truck source accepted')
        source[case]={'relation':measured['relation_to_500ft'],
            'median_gap_m':measured['median_surface_gap_m'],
            'ego_x0_m':native[0]['ego']['center_xy_m'][0],
            'ego_x479_m':native[-1]['ego']['center_xy_m'][0],
            'ego_speed_mps':native[0]['ego']['speed_mps'],
            'road_sha256':sha(root/'road.xodr')}
    a,b=source['probe_1'],source['probe_2']
    if (a['relation'],b['relation'])!=('above','below') or \
            (a['ego_x0_m'],a['ego_x479_m'],a['ego_speed_mps'],a['road_sha256'])!=(
             b['ego_x0_m'],b['ego_x479_m'],b['ego_speed_mps'],b['road_sha256']) or \
            not a['median_gap_m']>152.4>b['median_gap_m']:
        raise ValueError('Controlled same-road truck-gap pair differs')
    return {'passed':True,'cases':source,'physical_or_accepted_claim':False}


if __name__=='__main__':print(json.dumps(audit(),sort_keys=True))
