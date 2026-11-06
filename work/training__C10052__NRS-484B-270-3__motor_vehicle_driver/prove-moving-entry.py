"""Retained synthetic moving-entry pair for the NRS 484B.270(3) enter branch."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
ROOT=REPO/'.runtime-work/c10052/moving-entry-v1'
sys.path.insert(0,str(HERE/'native'))
from geometry import body
from measure_entry import measure,sha


def write(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def write_rows(path,values):
    path.write_text(''.join(json.dumps(value,allow_nan=False)+'\n' for value in values))


def build(name,enter):
    folder=ROOT/name
    folder.mkdir()
    source=HERE/'draft-facility/probe_a'
    samples=[json.loads(line) for line in (source/'native_samples.jsonl').read_text().splitlines()]
    for i,row in enumerate(samples):
        if enter:
            y=-1.5-2.5*min(1,max(0,(i-70)/60))
            x=row['native_center_xy_m'][0]
            row['native_center_xy_m']=[x,y]
            row['native_body_xy_m']=body(x,y)
            row['native_lane_id']=-2 if y<=-3 else -1
    write_rows(folder/'native_samples.jsonl',samples)
    shutil.copyfile(source/'road_geometry.json',folder/'road_geometry.json')
    write(folder/'entry-sources.json',{'format':'c10052-entry-sources-v1',
        'source_kind':'synthetic_cpu_fixture',
        'sha256':{filename:sha(folder/filename) for filename in
                  ('native_samples.jsonl','road_geometry.json')}})
    result=measure(folder)
    write(folder/'measurement.json',result)
    return result


def rejects(source,name,change,expected):
    folder=ROOT/name
    shutil.copytree(source,folder)
    if change=='bytes':
        path=folder/'native_samples.jsonl'
        path.write_bytes(path.read_bytes()+b' ')
    elif change=='kind':
        path=folder/'entry-sources.json'
        data=json.loads(path.read_text());data['source_kind']='original_native'
        write(path,data)
    else:
        raise ValueError('Unknown negative')
    try:measure(folder)
    except ValueError as error:
        if expected not in str(error):raise
    else:raise AssertionError('Entry negative was accepted')


def main():
    if ROOT.exists():raise ValueError('Retain prior entry proof')
    ROOT.mkdir(parents=True)
    baseline=build('no_entry',False)
    crossing=build('moving_entry',True)
    assert baseline['moving_entry_measured'] is False
    assert crossing['moving_entry_measured'] is True
    assert baseline['moving_occupied_frames']==0
    assert crossing['moving_occupied_frames']>0
    assert crossing['facility_designation_verified'] is False
    assert crossing['exception_a_observed']=='unresolved'
    rejects(ROOT/'moving_entry','changed_source','bytes','Entry source hash differs')
    rejects(ROOT/'moving_entry','synthetic_as_original','kind',
            'Synthetic entry samples cannot be original Native')
    summary={'format':'c10052-synthetic-moving-entry-proof-v1',
        'source_root':ROOT.relative_to(REPO).as_posix(),
        'cases':{name:{'measurement_sha256':sha(ROOT/name/'measurement.json'),
                       'source_manifest_sha256':sha(ROOT/name/'entry-sources.json')}
                 for name in ('no_entry','moving_entry')},
        'negative_count':2,'selected':False,'accepted':False}
    write(HERE/'moving-entry-summary.json',summary)
    print(json.dumps({'passed':True,'no_entry_frames':baseline['moving_occupied_frames'],
        'entry_frames':crossing['moving_occupied_frames'],
        'entry_frame':crossing['first_moving_entry_native_frame'],
        'negative_rejections':2},sort_keys=True))


if __name__=='__main__':main()
