"""Materialize two source-bound signal alternatives for CPU preflight."""
import hashlib
import json
from pathlib import Path
from branch_requests import HERE, ASSIGNMENT, source, CASES


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,obj):path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')


def build(suffixes=('signal_red_stop','signal_green_proceed')):
    assignment=source();base=HERE/'cases/branch-requests';road=base/'alley-signal.xodr'
    capture=(base/'signal_capture.py').read_text();check=(base/'signal_check.py').read_text()
    recording=json.loads((HERE/'config.json').read_text())['recording_description']
    output=[]
    for suffix in suffixes:
        if suffix not in CASES or CASES[suffix][0]!='signal_specific_307':
            raise ValueError('Unknown signal grid case')
        target=base/suffix;target.mkdir(parents=True,exist_ok=True)
        rows=[json.loads(line) for line in (base/(suffix+'.jsonl')).read_text().splitlines()]
        tracks=[]
        for row in rows:
            ego=row['ego']
            tracks.append({'frame':row['frame'],'time_s':row['time_s'],
                           'requested_ego_x_m':ego['requested_center_x_m'],
                           'requested_speed_mps':ego['requested_speed_mps'],
                           'requested_signal_aspect':row['device']['requested_signal_aspect'],
                           'source_kind':'authored_cpu_request','original_native_observed':False})
        (target/'requested-tracks.jsonl').write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in tracks))
        (target/'alley-stop.xodr').write_bytes(road.read_bytes())
        (target/'assignment-source.json').write_bytes(assignment.read_bytes())
        (target/'runner.py').write_text(capture)
        (target/'signal_check.py').write_text(check)
        aspect=CASES[suffix][1]
        cfg={'format':'c10389-signal-native-request-v1','assignment_id':ASSIGNMENT,
             'case_id':ASSIGNMENT+'__'+suffix,'candidate_id':'primary',
             'law_id':'NRS-484B-300-1','cell_id':'C10389','actor':'motor_vehicle_driver',
             'requested_signal_aspect':aspect,'camera_policy':'standard',
             'rate_hz':20,'frames':600,'duration_s':30,
             'road_sha256':sha(target/'alley-stop.xodr'),
             'tracks_sha256':sha(target/'requested-tracks.jsonl'),
             'official_placement_verified':False,'police_direction_verified':False,
             'original_native_observed':False,'recording_description':recording,
             'status':'authored_unselected_native_request'}
        write(target/'config.json',cfg)
        files=[{'path':name,'content':(target/name).read_text()} for name in
               ('runner.py','signal_check.py','config.json','assignment-source.json','alley-stop.xodr','requested-tracks.jsonl')]
        construction={'entrypoint':'runner.py','case_id':cfg['case_id'],'law_id':cfg['law_id'],
                      'cell_id':cfg['cell_id'],'actor':cfg['actor'],'files':files,
                      'recording_description':recording,'status':'unselected_cpu_construction'}
        write(target/'construction.json',construction)
        output.append({'case_id':cfg['case_id'],'construction_sha256':sha(target/'construction.json'),
                       'road_sha256':cfg['road_sha256'],'status':'unselected_cpu_construction'})
    return output


if __name__=='__main__':print(json.dumps(build(),sort_keys=True))
