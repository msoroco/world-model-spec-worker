"""Independent source and mutation audit for the saved traffic-pair rehearsal."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'native'))
from traffic_counterfactual import inspect


def expect_reject(absent,present,expected):
    try:
        inspect(absent,present)
    except ValueError as error:
        if expected not in str(error):
            raise
        return str(error)
    raise ValueError('Controlled negative unexpectedly passed: '+expected)


def mutate(path,change):
    rows=[json.loads(line) for line in path.read_text().splitlines()]
    change(rows)
    path.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))


def main():
    root=HERE/'exception-counterfactual-sources'
    proof=json.loads((HERE/'traffic-counterfactual-proof.json').read_text())
    actual={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()}
    if actual != proof['source_sha256']:
        raise ValueError('Saved controlled pair differs from proof hashes')
    absent,present=root/'absent',root/'present'
    result=inspect(absent,present)
    if (result['frames']!=480 or result['brake_onset_video_frame']!=120 or
        len(result['absent_ego_present_actor_overlap_frames'])!=41 or
        result['present_ego_present_actor_overlap_frames']!=[]):
        raise ValueError('Independent expected pair geometry differs')
    # Axis-aligned fixture permits an independent interval intersection count.
    a=[json.loads(line) for line in (absent/'native_samples.jsonl').read_text().splitlines()]
    c=[json.loads(line) for line in (present/'other_actor_history.jsonl').read_text().splitlines()]
    independently=[]
    for i,(ego,actor) in enumerate(zip(a,c)):
        e=ego['native_body_xy_m'];o=actor['body_xy_m']
        if (min(v[0] for v in e)<=max(v[0] for v in o) and
            min(v[0] for v in o)<=max(v[0] for v in e) and
            min(v[1] for v in e)<=max(v[1] for v in o) and
            min(v[1] for v in o)<=max(v[1] for v in e)):
            independently.append(i)
    if independently!=result['absent_ego_present_actor_overlap_frames']:
        raise ValueError('Independent rectangle intersection differs from saved processor')
    negatives=[]
    with tempfile.TemporaryDirectory(prefix='c110454-traffic-pair-') as temp:
        scratch=Path(temp)
        for name,relative,edit,expected in [
            ('construction_identity','present/capture_identity.json',None,'Controlled pair construction identity differs'),
            ('actor_frame','present/other_actor_history.jsonl',lambda r:r[200].update(native_frame=9999),'Controlled pair original frame/time join differs'),
            ('actor_shift','present/other_actor_history.jsonl',lambda r:[row.update(body_xy_m=[[x+20,y] for x,y in row['body_xy_m']]) for row in r],'Controlled no-brake path does not isolate avoided overlap'),
            ('missing_brake','present/native_samples.jsonl',lambda r:[row.update(conflict_brake_override=False,applied_brake=0) for row in r],'Controlled pair has no measured conflict brake response'),
            ('present_collision','present/native_samples.jsonl',lambda r:r[200].update(native_body_xy_m=a[200]['native_body_xy_m']),'Controlled no-brake path does not isolate avoided overlap'),
            ('initial_state','present/native_samples.jsonl',lambda r:r[0].update(native_center_xy_m=[-18,-1.75]),'Controlled pair initial ego state differs'),
        ]:
            pair=scratch/name
            shutil.copytree(root,pair)
            target=pair/relative
            if edit is None:
                packet=json.loads(target.read_text());packet['route_sha256']='0'*64
                target.write_text(json.dumps(packet)+'\n')
            else:
                mutate(target,edit)
            negatives.append({'name':name,'error':expect_reject(pair/'absent',pair/'present',expected)})
    return {'format':'lvmc-traffic-counterfactual-audit-v1','passed':True,
            'independent_overlap_frames':independently,'negative_cases':negatives,
            'source_hashes':actual,'physical_or_legal_necessity_claimed':False}


if __name__=='__main__':
    result=main()
    (HERE/'traffic-counterfactual-audit.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'passed':True,'independent_overlap_count':len(result['independent_overlap_frames']),
                      'negative_cases':len(result['negative_cases'])},indent=2))
