"""Authored CPU requests for statutory exception comparisons; not Native evidence."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
ASSIGNMENT=HERE.name
FRAMES=600
RATE=20
CASES={
    'signal_red_stop':('signal_specific_307','red','none',True),
    'signal_red_proceed':('signal_specific_307','red','none',False),
    'signal_green_stop':('signal_specific_307','green','none',True),
    'signal_green_proceed':('signal_specific_307','green','none',False),
    'officer_no_direction_stop':('police_direction','not_applicable','none',True),
    'officer_no_direction_proceed':('police_direction','not_applicable','none',False),
    'officer_directed_stop':('police_direction','not_applicable','proceed',True),
    'officer_directed_proceed':('police_direction','not_applicable','proceed',False),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source():
    path=ROOT/'inputs'/ASSIGNMENT/'assignment.json'
    assignment=json.loads(path.read_text())
    if sha(path)!='e34b92fea95ce943c8bee703c64285f568f4c5cfdb0a6b6428072f57dd846ee0':
        raise ValueError('Frozen assignment changed')
    law=assignment['law']['text']
    if hashlib.sha256(law.encode()).hexdigest()!='0083bdf940bab787cf1d1cf789a93d1edf516df1df6de3b3e91cca237c6bbba8':
        raise ValueError('Frozen law text changed')
    if assignment['cell']['layout']!='alley' or assignment['cell']['control']!='traffic_control_device' or assignment['actor']!='motor_vehicle_driver':
        raise ValueError('Frozen cell or actor changed')
    return path


def request(suffix):
    if suffix not in CASES:
        raise ValueError('Unknown statutory branch request')
    branch,signal,officer,stop=CASES[suffix]
    for frame in range(FRAMES):
        t=(frame+1)/RATE
        if stop:
            x=min(44.0,5.0+8.0*t)
            speed=0.0 if x>=44.0 else 8.0
        else:
            x=5.0+8.0*t
            speed=8.0
        yield {'case_id':ASSIGNMENT+'__'+suffix,'frame':frame,'time_s':t,
               'source_kind':'authored_cpu_request','target_branch':branch,
               'frozen_cell':{'layout':'alley','maneuver':'travel','control':'traffic_control_device'},
               'device':{'station_x_m':50.0,'requested_device_id':'3892' if branch=='signal_specific_307' else '3891',
                         'requested_road_sha256':sha(HERE/'cases/branch-requests/alley-signal.xodr') if branch=='signal_specific_307' else sha(HERE/'native/device/alley-stop.xodr'),
                         'requested_signal_aspect':signal,
                         'requested_official_placement':True,'official_placement_verified':False},
               'officer':{'requested_direction':officer,'police_authority_verified':False},
               'ego':{'requested_center_x_m':round(x,6),'requested_speed_mps':speed,
                      'requested_road_id':389,'requested_lane_id':-1},
               'original_native_observed':False,'legal_verdict':None}


def validate(rows,suffix):
    expected=list(request(suffix))
    if rows!=expected:
        raise ValueError('Authored statutory request differs from exact source-bound construction')
    stop=CASES[suffix][3]
    crossing=any(r['ego']['requested_center_x_m']>50 for r in rows)
    if stop==crossing:
        raise ValueError('Statutory branch contrast not requested')
    return {'case_id':ASSIGNMENT+'__'+suffix,'frames':FRAMES,'requested_crossing':crossing,
            'requested_stop':stop,'original_native_observed':False,'selected_delivery':False}


def build(destination):
    source_path=source();destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    entries=[]
    for suffix in CASES:
        rows=list(request(suffix));review=validate(rows,suffix)
        path=destination/(suffix+'.jsonl')
        if path.exists() and path.read_text().splitlines()!=[json.dumps(row,sort_keys=True) for row in rows]:
            raise ValueError('Existing authored request differs: '+suffix)
        path.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))
        entries.append({'suffix':suffix,'case_id':review['case_id'],'path':path.name,
                        'sha256':sha(path),'review':review})
    return {'format':'c10389-statutory-branch-requests-v1','assignment_id':ASSIGNMENT,
            'frozen_assignment_sha256':sha(source_path),'entries':entries,
            'comparisons':[['signal_red_stop','signal_red_proceed','signal_green_stop','signal_green_proceed'],
                           ['officer_no_direction_stop','officer_no_direction_proceed','officer_directed_stop','officer_directed_proceed']],
            'source_kind':'authored_cpu_request','native_executed':False,
            'selected_delivery':False}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    args=parser.parse_args();print(json.dumps(build(args.output),sort_keys=True))
