"""Three source-triggered Native motion alternatives for the officer probe."""
import copy
import hashlib
import json
from pathlib import Path

from build_reference_fallbacks import DEFAULT, OPTIONS

HERE=Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


def build():
    draft=json.loads((HERE/'draft-officer-direction-manifest.json').read_text())
    entry=copy.deepcopy(draft['cases'][0])
    primary=json.loads((HERE/entry['construction']).read_text())
    if sha(HERE/entry['construction'])!=entry['construction_sha256']:
        raise ValueError('Officer primary changed before fallback construction')
    entry['candidate_risk']={
        'status':'physical',
        'reason':'Stop-point overshoot, insufficient stopped samples and follower closing remain distinct risks while the pedestrian actor source is held fixed.'}
    candidates=[]
    for ident,changes,reason,source,metric,failure in OPTIONS:
        construction=copy.deepcopy(primary)
        config_file=next(row for row in construction['files'] if row['path']=='config.json')
        config=json.loads(config_file['content'])
        config['candidate_id']=ident
        config['controller_tuning']={**DEFAULT,**changes}
        config_file['content']=json.dumps(config,indent=2,sort_keys=True)+'\n'
        construction['candidate_id']=ident
        construction['status']='draft_fallback_cpu_preparation_incomplete'
        construction['mechanisms']=primary['mechanisms']+[
            ident+': '+reason+'; controller tuning '+json.dumps(changes,sort_keys=True)]
        name='draft-officer-direction-'+ident+'-construction.json'
        write(HERE/name,construction)
        candidates.append({'id':ident,'construction':name,
            'construction_sha256':sha(HERE/name),
            'trigger':{'source':source,'metric':metric,
                       'failure_condition':failure},
            'changed_knobs':[key+': '+str(DEFAULT[key])+' -> '+str(value)
                             for key,value in changes.items()]})
    entry['candidates']=candidates
    draft['cases']=[entry]
    draft['status']='draft_officer_direction_four_candidate_diagnostic'
    name=HERE/'draft-officer-direction-fallback-manifest.json'
    write(name,draft)
    return {'manifest_sha256':sha(name),
            'candidates':{row['id']:row['construction_sha256'] for row in candidates}}


if __name__=='__main__':
    print(json.dumps(build(),sort_keys=True))
