"""Measure three isolated rider fallback triggers on source-hashed 480-frame variants."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
from geometry import body
from measure_facility import overlap_area
from rider_engineering import CONFLICT_BOUNDS_M
from rider_candidates import evaluate_sources


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,data):path.write_text(json.dumps(data,indent=2)+'\n')


def main():
    prototype=json.loads((HERE/'rider-timing-prototype.json').read_text())
    scratch=ROOT/'.runtime-work/c10052-rider-trigger-sources'
    scratch.mkdir(parents=True,exist_ok=True)
    results=[]
    for receipt in prototype['receipts']:
        case=receipt['case'];kind,response=case.rsplit('-',1)
        source=ROOT/receipt['sources']['samples']
        base=[json.loads(line) for line in source.read_text().splitlines()]
        expected=next(r['native_frame'] for r in base
                      if overlap_area(r['ego_body_xy'],CONFLICT_BOUNDS_M)>.01)
        for fixture in ('baseline','short_runway','late_entry','occluded'):
            rows=json.loads(json.dumps(base))
            if fixture=='short_runway':
                for i in range(15):
                    x=-40+i/15
                    rows[i]['ego_body_xy']=body(x,-1.5)
                    rows[i]['ego_route_index']=round((x+45)*10)
                    rows[i]['ego_speed_mps']=4/3
            if fixture=='late_entry':
                fields=('ego_body_xy','ego_route_index','ego_native_road_id','ego_speed_mps')
                for i,row in enumerate(rows):
                    prior=base[max(0,i-8)]
                    for field in fields:row[field]=prior[field]
            rider=[i for i,row in enumerate(rows)
                   if overlap_area(row['rider_body_xy'],CONFLICT_BOUNDS_M)>.01]
            hidden=set(rider[:7]) if fixture=='occluded' else set()
            visibility=[{'native_frame':row['native_frame'],'time_s':row['time_s'],
                         'rider_and_ego_body_visible':i not in hidden}
                        for i,row in enumerate(rows)]
            folder=scratch/(case+'-'+fixture);folder.mkdir(exist_ok=True)
            samples=folder/'native_rider_ego_samples.jsonl'
            camera=folder/'camera_visibility.jsonl'
            samples.write_text(''.join(json.dumps(row,separators=(',',':'))+'\n' for row in rows))
            camera.write_text(''.join(json.dumps(row,separators=(',',':'))+'\n' for row in visibility))
            manifest=folder/'rider-trigger-sources.json'
            write(manifest,{'source_kind':'synthetic_cpu_fixture','case_id':case,
                            'fixture':fixture,'expected_ego_frame':expected,
                            'sha256':{p.name:sha(p) for p in (samples,camera)},
                            'accepted':False})
            result=evaluate_sources(folder)
            triggers=[result[f'fallback{i}_trigger_measured'] for i in (1,2,3)]
            assert triggers=={
                'baseline':[False,False,False],
                'short_runway':[True,False,False],
                'late_entry':[False,True,False],
                'occluded':[False,False,True]}[fixture]
            changed=folder/'camera_visibility.jsonl'
            changed.write_text(changed.read_text()+' ')
            try:evaluate_sources(folder)
            except ValueError as exc:assert 'source hash differs' in str(exc)
            else:raise AssertionError('Changed visibility accepted')
            changed.write_text(''.join(json.dumps(row,separators=(',',':'))+'\n' for row in visibility))
            results.append({'case':case,'fixture':fixture,
                            'source_manifest_sha256':sha(manifest),**result})
    summary={'format':'c10052-rider-fallback-trigger-proof-v1','passed':True,
             'rows':results,'isolated_crossings':18,'changed_visibility_negatives':24,
             'prototype_sha256':sha(HERE/'rider-timing-prototype.json'),
             'selected':False,'accepted':False}
    write(HERE/'rider-fallback-trigger-proof.json',summary)
    print(json.dumps({'passed':True,'rows':len(results),'isolated_crossings':18,
                      'changed_visibility_negatives':24},indent=2))


if __name__=='__main__':main()
