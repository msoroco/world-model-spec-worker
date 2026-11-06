"""Build matched synthetic CPU corridor sources for exception A timing logic."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
ROOT=REPO/'.runtime-work/c10052/alley-transition-v1'
sys.path.insert(0,str(HERE/'native'))
from geometry import body
from measure_alley_transition import measure


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,obj):path.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')


def build(name,x):
    folder=ROOT/name;folder.mkdir()
    geometry={'road_id':1,'driving_lane_id':-1,'bicycle_lane_id':-2,
        'bicycle_facility_native_xy_bounds_m':[-60,-5,60,-3],
        'alley_entrance_native_xy_bounds_m':[-3,-14,3,-5],
        'native_facility_design_verified':False}
    write(folder/'road_geometry.json',geometry)
    rows=[]
    for i in range(480):
        y=-1.5-6.5*min(1,max(0,(i-60)/100))
        rows.append({'native_frame':100+i,'time_s':round((i+1)/20,6),
            'native_center_xy_m':[x,y],
            'native_body_xy_m':body(x,y),
            'speed_mps':1.3 if 60<=i<160 else 0,
            'synthetic_diagnostic':True})
    (folder/'native_samples.jsonl').write_text(''.join(
        json.dumps(row,allow_nan=False)+'\n' for row in rows))
    write(folder/'alley-transition-sources.json',{
        'format':'c10052-alley-transition-sources-v1',
        'source_kind':'synthetic_cpu_fixture',
        'sha256':{name:sha(folder/name) for name in
                  ('native_samples.jsonl','road_geometry.json')}})
    result=measure(folder);write(folder/'measurement.json',result)
    return result


def reject(source,name,mode,expected):
    target=ROOT/name;shutil.copytree(source,target)
    if mode=='changed_samples':
        path=target/'native_samples.jsonl';path.write_bytes(path.read_bytes()+b' ')
    elif mode=='relabeled':
        path=target/'alley-transition-sources.json';manifest=json.loads(path.read_text())
        manifest['source_kind']='original_native';write(path,manifest)
    else:raise ValueError('Unknown negative')
    try:measure(target)
    except ValueError as error:
        if expected not in str(error):raise
    else:raise AssertionError('Alley transition negative passed')


def main():
    if ROOT.exists():raise ValueError('Retain prior alley transition proof')
    ROOT.mkdir(parents=True)
    near=build('near_alley',0)
    away=build('away_from_alley',-12)
    assert near['time_bounded_geometry_candidate'] is True
    assert away['time_bounded_geometry_candidate'] is False
    assert near['simultaneous_moving_overlap_frames']>0
    assert away['simultaneous_moving_overlap_frames']==0
    assert near['first_facility_entry_native_frame']==away['first_facility_entry_native_frame']
    reject(ROOT/'near_alley','changed_samples','changed_samples','source hash differs')
    reject(ROOT/'near_alley','relabeled','relabeled','provenance unverified')
    summary={'format':'c10052-alley-transition-synthetic-proof-v1',
        'source_root':ROOT.relative_to(REPO).as_posix(),
        'cases':{name:{'measurement_sha256':sha(ROOT/name/'measurement.json'),
            'source_manifest_sha256':sha(ROOT/name/'alley-transition-sources.json')}
            for name in ('near_alley','away_from_alley')},
        'negative_count':2,'selected':False,'accepted':False}
    write(HERE/'alley-transition-summary.json',summary)
    print(json.dumps({'passed':True,'near':near,'away':away,'negatives':2},sort_keys=True))


if __name__=='__main__':main()
