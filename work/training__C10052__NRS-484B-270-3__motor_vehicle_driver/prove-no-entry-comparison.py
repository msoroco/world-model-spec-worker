"""Controlled same-time/x synthetic lateral-entry contrast for the enter clause."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE/'no-entry-comparison-sources'
NAMES=('primary','fallback1','fallback2','fallback3')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):path.write_text(json.dumps(value,sort_keys=True)+'\n')


def load(path):
    spec=importlib.util.spec_from_file_location('no_entry_exact_meter',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def main():
    ROOT.mkdir(exist_ok=True)
    baseline=[json.loads(line) for line in (HERE/'no-entry-sources/native_samples.jsonl').read_text().splitlines()]
    altered=[]
    for i,row in enumerate(baseline):
        row=json.loads(json.dumps(row))
        phase=max(0,min(1,(i-120)/160))
        y=-1.5-2.7*math.sin(math.pi*phase)**2 if 120<i<280 else -1.5
        x=row['native_center_xy_m'][0]
        row['native_center_xy_m']=[x,round(y,6)]
        row['native_body_xy_m']=[[round(x-2.6,6),round(y-1.1,6)],
                                 [round(x+2.6,6),round(y-1.1,6)],
                                 [round(x+2.6,6),round(y+1.1,6)],
                                 [round(x-2.6,6),round(y+1.1,6)]]
        row['native_lane_id']=-2 if y<=-3 else -1
        altered.append(row)
    (ROOT/'entry').mkdir(exist_ok=True)
    (ROOT/'entry/native_samples.jsonl').write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in altered))
    (ROOT/'entry/road_geometry.json').write_bytes((HERE/'no-entry-sources/road_geometry.json').read_bytes())
    write(ROOT/'entry/entry-sources.json',{'format':'c10052-entry-sources-v1',
        'source_kind':'synthetic_cpu_fixture',
        'sha256':{name:sha(ROOT/'entry'/name) for name in ('native_samples.jsonl','road_geometry.json')}})
    manifest=json.loads((HERE/'draft-no-entry-execution-manifest.json').read_text())
    entry=manifest['cases'][0]
    results=[]
    for name in NAMES:
        ref=entry if name=='primary' else next(c for c in entry['candidates'] if c['id']==name)
        construction=HERE/ref['construction']
        if sha(construction)!=ref['construction_sha256']:
            raise ValueError('Exact paired candidate construction changed')
        files=json.loads(construction.read_text())['files']
        meter=[f['content'] for f in files if f['path']=='measure_entry.py']
        if len(meter)!=1:raise ValueError('Exact paired meter missing')
        local=ROOT/('meter-'+name+'.py');local.write_text(meter[0])
        import sys
        sys.path.insert(0,str(HERE/'native'))
        module=load(local)
        absent=module.measure(HERE/'no-entry-sources')
        present=module.measure(ROOT/'entry')
        if (absent['moving_entry_measured'] is not False or
            present['moving_entry_measured'] is not True or
            absent['moving_occupied_frames']!=0 or
            present['moving_occupied_frames']<=0):
            raise ValueError('Controlled pair did not isolate facility entry')
        results.append({'candidate':name,'construction_sha256':ref['construction_sha256'],
                        'meter_sha256':sha(local),
                        'no_entry_moving_frames':absent['moving_occupied_frames'],
                        'entry_moving_frames':present['moving_occupied_frames'],
                        'first_entry_native_frame':present['first_moving_entry_native_frame']})
        local.unlink()
        sys.path.pop(0)
    proof={'format':'c10052-controlled-no-entry-comparison-v1','passed':True,
        'fixed_inputs':['original frame indices','50 ms times','longitudinal center x',
                        'authored facility bounds','candidate engineering identity'],
        'changed_input':'lateral center/body path into bicycle facility',
        'entry_source_sha256':{name:sha(ROOT/'entry'/name) for name in
                               ('native_samples.jsonl','road_geometry.json','entry-sources.json')},
        'candidate_pairs':results,'selected':False,'physical_or_legal_verdict_claimed':False}
    write(HERE/'no-entry-comparison-proof.json',proof)
    return proof


if __name__=='__main__':
    proof=main()
    print(json.dumps({'passed':True,'candidate_pairs':len(proof['candidate_pairs']),
                      'entry_moving_frames':proof['candidate_pairs'][0]['entry_moving_frames']},indent=2))
