"""Three source-triggered alternate constructions per draft sweep case."""
import copy
import hashlib
import json
from pathlib import Path

from candidate_tuning import tuning

HERE = Path(__file__).resolve().parent
FALLBACKS = ('fallback1','fallback2','fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def build():
    primary=json.loads((HERE/'sweep-primary-compatibility-manifest.json').read_text())
    entries=[]
    for source in primary['cases']:
        cid=source['case_id'];base=HERE/source['construction']
        if sha(base)!=source['construction_sha256']:
            raise ValueError('Draft primary construction changed: '+cid)
        original=json.loads(base.read_text())
        config=json.loads(next(f['content'] for f in original['files'] if f['path']=='config.json'))
        axis=next(iter(config['sweep']['sweep_point']))
        candidates=[]
        for name in FALLBACKS:
            selected=tuning(name)
            changed=copy.deepcopy(selected.risk_trigger['changed_knobs'])
            if axis=='following_gap_m' and name=='fallback3':
                changed.remove('follower_brake_gap_m')
            trigger=copy.deepcopy(selected.risk_trigger)
            trigger['changed_knobs']=changed
            construction=copy.deepcopy(original)
            bundle_config=copy.deepcopy(config)
            bundle_config['candidate_id']=name
            bundle_config['candidate_risk_trigger']=trigger
            next(f for f in construction['files'] if f['path']=='config.json')['content']=json.dumps(
                bundle_config, indent=2, sort_keys=True)+'\n'
            construction.update(candidate_id=name,risk_trigger=trigger,
                                fallback_changed_knobs=changed,
                                parent_primary_sha256=sha(base))
            path=HERE/('sweep-'+cid+'-'+name+'-construction.json')
            write(path,construction)
            candidates.append({'id':name,'construction':path.name,
                               'construction_sha256':sha(path),
                               'trigger':trigger,'changed_knobs':changed})
        entry=copy.deepcopy(source)
        entry['candidate_risk']={'status':'physical',
            'reason':'Surveyed spawn clearance, ego stop overshoot and follower closing are original-source measurable risks; the sweep axis remains fixed.'}
        entry['candidates']=candidates
        entries.append(entry)
    if len(entries)!=9 or any(len(e['candidates'])!=3 for e in entries):
        raise ValueError('Nine primary plus three-fallback sweep cases required')
    manifest=dict(primary,status='draft_sweep_candidate_cpu_diagnostic',cases=entries)
    path=HERE/'sweep-candidate-manifest.json';write(path,manifest)
    return {'manifest':path.name,'manifest_sha256':sha(path),
            'cases':len(entries),'fallbacks':sum(len(e['candidates']) for e in entries)}


if __name__=='__main__':
    print(json.dumps(build(),indent=2,sort_keys=True))
