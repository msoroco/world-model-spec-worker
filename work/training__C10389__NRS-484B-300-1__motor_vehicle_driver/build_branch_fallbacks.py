"""Raise the overview camera for branch cases without changing legal contrast."""
import hashlib
import json
from pathlib import Path
import shutil
from branch_requests import HERE


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,obj):path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')


def build(suffixes=('signal_red_stop','signal_green_proceed','officer_no_direction_stop','officer_directed_proceed')):
    base=HERE/'cases/branch-requests';entries=[]
    for suffix in suffixes:
        source=base/suffix;target=base/(suffix+'-fallback1');target.mkdir(parents=True,exist_ok=True)
        for name in ('runner.py','signal_check.py' if suffix.startswith('signal_') else 'officer_check.py',
                     'assignment-source.json','alley-stop.xodr','requested-tracks.jsonl'):
            shutil.copyfile(source/name,target/name)
        cfg=json.loads((source/'config.json').read_text());cfg['candidate_id']='fallback1'
        cfg['camera_policy']='elevated_overview';cfg['fallback_trigger']='Original device/officer source face or body not legible in overview'
        write(target/'config.json',cfg)
        names=('runner.py','signal_check.py' if suffix.startswith('signal_') else 'officer_check.py',
               'config.json','assignment-source.json','alley-stop.xodr','requested-tracks.jsonl')
        original=json.loads((source/'construction.json').read_text())
        original['files']=[{'path':name,'content':(target/name).read_text()} for name in names]
        write(target/'construction.json',original)
        entries.append({'case_id':cfg['case_id'],'candidate_id':'fallback1','construction_sha256':sha(target/'construction.json'),
                        'changed_knobs':['camera_policy'],'source_tracks_sha256':cfg['tracks_sha256']})
    return entries


if __name__=='__main__':print(json.dumps(build(),sort_keys=True))
