"""Positive and missing-source diagnostics for every exact saved measurement.

Fake camera bytes test source binding only, not media decode or physical coverage.
"""
from __future__ import annotations
import hashlib
import json
import math
import tempfile
from pathlib import Path
from saved_measurement import read_attempt, REQUIRED

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
CAMERAS=('overview','approach','reference_corner','driver_reference')

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def path_at(route, fraction):
    points=[tuple(map(float,p)) for p in route]
    lengths=[math.dist(a,b) for a,b in zip(points,points[1:])]
    length=sum(lengths)
    target=fraction*length
    for a,b,span in zip(points,points[1:],lengths):
        if target <= span:
            t=target/span
            return [a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])]
        target-=span
    return list(points[-1])

def fixture(root,scene):
    (root/'acquisition-provenance.json').write_text(json.dumps({'provenance_kind':'synthetic_fixture','diagnostic_fixture':True})+'\n')
    (root/'scene.json').write_text(json.dumps(scene)+'\n')
    rows=[];joins=[]
    for i in range(201):
        frame=1000+i;time_s=i*.05
        rows.append({'frame':frame,'time_s':time_s,'source':'original_native',
                     'actor_id':7,'body_center_xy_m':path_at(scene['route_xy_m'],i/200)})
        joins.append({'frame':frame,'time_s':time_s,'cameras':{name:i for name in CAMERAS}})
    (root/'walker-body-history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
    (root/'camera-frame-joins.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in joins))
    for name in CAMERAS:
        (root/(name+'.mkv')).write_bytes(('FAKE DIAGNOSTIC CAMERA BYTES '+name).encode())
    index={name:{'kind':'diagnostic_fixture','sha256':sha(root/name)} for name in REQUIRED}
    (root/'acquisition.json').write_text(json.dumps(index)+'\n')


def prove():
    work=REPO/'.runtime-work';work.mkdir(exist_ok=True)
    findings={}
    for scene_path in sorted((ROOT/'cases').glob('*/scene.json')):
        scene=json.loads(scene_path.read_text());name=scene_path.parent.name
        with tempfile.TemporaryDirectory(dir=work,prefix='c227749-'+name+'-') as temp:
            root=Path(temp);fixture(root,scene)
            report=read_attempt(root)
            if not report['diagnostic_fixture'] or report['measurement']['original_frame_count']!=201:
                raise ValueError(name+': diagnostic proof incomplete')
            (root/'walker-body-history.jsonl').unlink()
            try: read_attempt(root)
            except ValueError as error:
                if 'Missing required source: walker-body-history.jsonl' not in str(error):
                    raise
                rejection=str(error)
            else: raise ValueError(name+': missing required source accepted')
            findings[name]={'case_id':scene['case_id'],'positive':'passed',
                            'negative_rejection':rejection,
                            'diagnostic_fixture':True,
                            'original_frame_count':201,
                            'full_video_decode':'not_attempted',
                            'physical_visibility':'unconfirmed'}
    return findings

if __name__=='__main__': print(json.dumps(prove(),indent=2))
