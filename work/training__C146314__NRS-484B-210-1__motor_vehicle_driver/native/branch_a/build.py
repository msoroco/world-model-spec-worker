"""Author exact-source paragraph (a) left-signal controlled requests."""
import hashlib
import json
from pathlib import Path

BRANCH=Path(__file__).resolve().parent
NATIVE=BRANCH.parent
CASE=NATIVE.parent
ROOT=CASE.parents[1]
CANDIDATES=('primary','fallback1','fallback2','fallback3')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def write_rows(path,values):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(x,sort_keys=True,allow_nan=False)+'\n'
                            for x in values))

def build():
    plan=read(CASE/'case-plan.json')
    if 'When the driver of the vehicle overtaken is making or signaling to make a left turn.' not in plan['source_law']['text']:
        raise ValueError('paragraph (a) source differs')
    entries=[]
    for witness,signal in (('exception_1_1',False),('exception_1_2',True)):
        for candidate in CANDIDATES:
            template=NATIVE/'drafts/witness_1'/candidate
            src_cfg=read(template/'config.json')
            src_rows=rows(template/'requested-tracks.jsonl')
            target=BRANCH/'drafts'/witness/candidate
            case_id=CASE.name+'__'+witness
            generated=[]
            for row in src_rows:
                row=dict(row)
                row['case_id']=case_id
                row['lead_left_signal_requested']=signal
                row['source_branch']='NRS 484B.210(1)(a)'
                generated.append(row)
            track=target/'requested-tracks.jsonl'
            write_rows(track,generated)
            cfg=dict(src_cfg)
            cfg.update(format='c146314-paragraph-a-request-v1',
                case_id=case_id,tracks_sha256=sha(track),
                lead_left_signal_requested=signal,
                source_branch='NRS 484B.210(1)(a)',
                status='unselected_native_request')
            write(target/'config.json',cfg)
            entries.append({'case_id':case_id,'candidate_id':candidate,
                'lead_left_signal_requested':signal,
                'config_sha256':sha(target/'config.json'),
                'tracks_sha256':sha(track),
                'status':'unselected_native_request'})
    manifest={'format':'c146314-paragraph-a-construction-v1',
        'assignment_id':CASE.name,
        'assignment_sha256':sha(ROOT/'inputs'/CASE.name/'assignment.json'),
        'case_plan_sha256':sha(CASE/'case-plan.json'),
        'road_sha256':sha(NATIVE/'one-way-pass.xodr'),
        'capture_sha256':sha(NATIVE/'capture.py'),
        'entries':entries,'original_native_observed':False,
        'delivery_ready':False}
    write(BRANCH/'manifest.json',manifest)
    return manifest

if __name__=='__main__':
    print(json.dumps({'requests':len(build()['entries'])}))
