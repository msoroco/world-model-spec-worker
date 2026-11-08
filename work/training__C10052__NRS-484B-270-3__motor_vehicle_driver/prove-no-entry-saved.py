"""Retained straight-through no-entry source and exact-candidate saved proofs."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile

HERE=Path(__file__).resolve().parent
SOURCE=HERE/'no-entry-sources'
NAMES=('primary','fallback1','fallback2','fallback3')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):path.write_text(json.dumps(value,sort_keys=True)+'\n')


def load(path):
    spec=importlib.util.spec_from_file_location('exact_no_entry_meter',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def source():
    SOURCE.mkdir(exist_ok=True)
    geometry=HERE/'draft-facility/probe_a/road_geometry.json'
    shutil.copyfile(geometry,SOURCE/'road_geometry.json')
    rows=[]
    for index in range(480):
        x=-45+60*index/479
        body=[[round(x-2.6,6),-2.6],[round(x+2.6,6),-2.6],
              [round(x+2.6,6),-.4],[round(x-2.6,6),-.4]]
        rows.append({'native_frame':1000+index,'time_s':round((index+1)*.05,5),
                     'native_center_xy_m':[round(x,6),-1.5],
                     'native_body_xy_m':body,'speed_mps':2.5,
                     'native_road_id':1,'native_lane_id':-1,
                     'synthetic_diagnostic':True})
    (SOURCE/'native_samples.jsonl').write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))
    write(SOURCE/'entry-sources.json',{'format':'c10052-entry-sources-v1',
        'source_kind':'synthetic_cpu_fixture',
        'sha256':{name:sha(SOURCE/name) for name in ('native_samples.jsonl','road_geometry.json')}})
    return rows


def rejected(meter,folder,expected):
    try:meter.measure(folder)
    except (ValueError,FileNotFoundError) as error:
        if expected not in str(error):raise
        return str(error)
    raise ValueError('No-entry saved negative passed unexpectedly')


def main():
    rows=source()
    manifest=json.loads((HERE/'draft-no-entry-execution-manifest.json').read_text())
    entry=manifest['cases'][0]
    results=[]
    with tempfile.TemporaryDirectory(prefix='c10052-no-entry-saved-') as temp:
        root=Path(temp)
        for candidate in NAMES:
            ref=entry if candidate=='primary' else next(x for x in entry['candidates'] if x['id']==candidate)
            construction_path=HERE/ref['construction']
            if sha(construction_path)!=ref['construction_sha256']:
                raise ValueError('Exact no-entry candidate hash differs')
            construction=json.loads(construction_path.read_text())
            bundle=root/candidate/'bundle';bundle.mkdir(parents=True)
            for item in construction['files']:
                target=bundle/item['path'];target.parent.mkdir(parents=True,exist_ok=True)
                target.write_text(item['content'])
            import sys
            sys.path.insert(0,str(bundle))
            meter=load(bundle/'measure_entry.py')
            positive=meter.measure(SOURCE)
            if (positive['moving_entry_measured'] is not False or
                positive['moving_occupied_frames']!=0 or
                positive['driving_lane_observed'] is not True or
                positive['bicycle_lane_observed'] is not False):
                raise ValueError('Straight-through source entered the facility')
            negative=root/candidate/'negative';shutil.copytree(SOURCE,negative)
            (negative/'entry-sources.json').unlink()
            missing=rejected(meter,negative,'entry-sources.json')
            tampered=root/candidate/'tampered';shutil.copytree(SOURCE,tampered)
            (tampered/'native_samples.jsonl').write_bytes((tampered/'native_samples.jsonl').read_bytes()+b' ')
            changed=rejected(meter,tampered,'Entry source hash differs')
            results.append({'candidate':candidate,'construction_sha256':ref['construction_sha256'],
                'meter_sha256':sha(bundle/'measure_entry.py'),
                'moving_entry_measured':False,'moving_occupied_frames':0,
                'missing_source_negative':missing,'changed_byte_negative':changed})
            sys.path.pop(0)
    proof={'format':'c10052-no-entry-exact-saved-proof-v1','passed':True,
           'manifest_sha256':sha(HERE/'draft-no-entry-execution-manifest.json'),
           'source_sha256':{name:sha(SOURCE/name) for name in
                            ('native_samples.jsonl','road_geometry.json','entry-sources.json')},
           'first_center_xy_m':rows[0]['native_center_xy_m'],
           'last_center_xy_m':rows[-1]['native_center_xy_m'],
           'candidates':results,'selected':False,'physical_observation_claimed':False}
    write(HERE/'no-entry-saved-proof.json',proof)
    return proof


if __name__=='__main__':
    result=main()
    print(json.dumps({'passed':result['passed'],'candidate_count':len(result['candidates']),
                      'moving_entry_measured':False},indent=2))
