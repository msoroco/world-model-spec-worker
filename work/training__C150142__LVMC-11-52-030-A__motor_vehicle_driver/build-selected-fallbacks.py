"""Bind three same-case physical-risk alternatives to a selected witness."""
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


RISKS={
    'fallback1':{'source':'Native actor centers and red-paint extent',
        'metric':'longitudinal parking overshoot in m',
        'failure_condition':'Observed ego body passes the intended parking target before stopping',
        'changed_knobs':['requested_approach_frames','controller approach speed']},
    'fallback2':{'source':'decoded overview source-camera pixels',
        'metric':'visible red paint and complete ego body in overview',
        'failure_condition':'Paint or ego body is obscured in source overview frames',
        'changed_knobs':['overview camera elevation']},
    'fallback3':{'source':'Native stationary body center and four-view frame join',
        'metric':'stationary observed red-curb interval in frames',
        'failure_condition':'Observed stopped interval is too short for manual parking review',
        'changed_knobs':['requested_approach_frames','controller approach speed']}}


def build(witness='reference'):
    if witness not in ('reference','contrast'):
        raise ValueError('Unknown red-curb witness')
    selected=ROOT/'selected-primary'/witness
    case_id=ROOT.name+'__'+witness
    primary=json.loads((selected/'construction.json').read_text())
    if primary['case_id']!=case_id:raise ValueError('Selected witness construction differs')
    files={item['path']:item['content'] for item in primary['files']}
    config=json.loads(files['config.json'])
    entries=[]
    for candidate,risk in RISKS.items():
        draft=ROOT/'native/drafts'/witness/candidate
        draft_config=json.loads((draft/'config.json').read_text())
        alt=copy.deepcopy(primary)
        alt_files={item['path']:item for item in alt['files']}
        candidate_config=copy.deepcopy(config)
        for key in ('candidate_id','tracks_sha256','requested_approach_frames',
                    'camera_policy','risk_trigger'):
            candidate_config[key]=draft_config[key]
        alt_files['config.json']['content']=json.dumps(candidate_config,indent=2)+'\n'
        alt_files['requested-tracks.jsonl']['content']=(draft/'requested-tracks.jsonl').read_text()
        path=ROOT/'selected-fallbacks'/witness/candidate/'construction.json'
        write(path,alt)
        entries.append({'id':candidate,'construction':path.relative_to(ROOT).as_posix(),
            'construction_sha256':sha(path),
            'trigger':{key:risk[key] for key in ('source','metric','failure_condition')},
            'changed_knobs':risk['changed_knobs']})
    manifest_path=selected/'draft-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    manifest['cases'][0]['candidates']=entries
    write(manifest_path,manifest)
    return {'case_id':case_id,'fallbacks':[{key:item[key] for key in
            ('id','construction_sha256')} for item in entries],
            'original_native_observed':False}


if __name__=='__main__':print(json.dumps(build(sys.argv[1] if len(sys.argv)>1 else 'reference'),sort_keys=True))
