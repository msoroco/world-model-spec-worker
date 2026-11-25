"""Source-shaped vehicle-operation and ownership lifecycle CPU fixtures."""
import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EVENTS=['capture_finished','encoders_closed','restoration_verified',
        'native_exit','owner_released','saved_processing_started']


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove(short,kind):
    if short not in ('reference','contrast'):raise ValueError('Unknown exact case')
    manifest=json.loads((ROOT/'execution-manifest.json').read_text())
    case=next(x for x in manifest['cases'] if x['case_id'].endswith('__'+short))
    recipe=json.loads((ROOT/f'fixture-recipe-{short}.json').read_text())
    spec_path=ROOT/f'diagnostic-{short}.json'
    if sha(spec_path)!=recipe['generator']['sha256']:
        raise ValueError('Diagnostic source recipe changed')
    spec=json.loads(spec_path.read_text())
    base={'case_id':case['case_id'],'construction_sha256':case['construction_sha256'],
          'provenance_kind':'synthetic_fixture','diagnostic_fixture':True,
          'original_native_motion_verified':False,'legal_verdict_claimed':False,
          'driver_attention_to_operation':None}
    if kind=='lifecycle':return dict(base,events=EVENTS,exit_code=0)
    if kind not in ('complete_motion','incomplete_motion','missing_evidence'):
        raise ValueError('Unknown fixture kind')
    source=spec['files']['native-ego-frames.jsonl']
    rows=[json.loads(s) for s in source.splitlines()]
    mapping=[json.loads(s) for s in spec['files']['video_frames.jsonl'].splitlines()]
    if len(rows)!=600 or len(mapping)!=600:
        raise ValueError('Complete diagnostic source changed')
    if kind=='incomplete_motion':rows=rows[:150]
    if kind=='missing_evidence':rows=[]
    joined=bool(rows) and all(r['native_frame']==m['native_frame'] and
                              abs(r['time_s']-m['time_s'])<1e-6
                              for r,m in zip(rows,mapping))
    progress=(math.dist(rows[0]['position_m'][:2],rows[-1]['position_m'][:2])
              if rows else 0.)
    complete=len(rows)==600 and joined and progress>=75.
    status='unverified' if not rows else 'met' if complete else 'not_met'
    return dict(base,physical_checks={'maneuver':{
        'status':status,'method':'original-shaped Native position/frame join and 75 m engineering progress',
        'sources':['diagnostic-'+short+'.json/native-ego-frames.jsonl',
                   'diagnostic-'+short+'.json/video_frames.jsonl'],
        'details':{'sample_count':len(rows),'progress_m':progress,
                   'joined':joined,'not_a_legal_threshold':True}}},
        maneuver_completed=complete,
        realized_observables=({'sample_count':len(rows),'progress_m':progress,
                               'joined':joined} if rows else {}),
        source_sha256={'native-ego-frames.jsonl':hashlib.sha256(source.encode()).hexdigest(),
                       'video_frames.jsonl':hashlib.sha256(spec['files']['video_frames.jsonl'].encode()).hexdigest()})


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',required=True)
    parser.add_argument('--kind',required=True);parser.add_argument('--output',required=True)
    a=parser.parse_args();r=prove(a.case,a.kind)
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'case_id':r['case_id'],'kind':a.kind,
                      'status':r.get('physical_checks',{}).get('maneuver',{}).get('status','lifecycle'),
                      'original_native_motion_verified':False}))


if __name__=='__main__':main()
