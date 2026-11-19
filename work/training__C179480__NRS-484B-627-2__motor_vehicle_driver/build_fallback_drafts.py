"""Build exact risk-triggered fallback bundles from current primary sources."""
import hashlib
import json
from pathlib import Path

from candidate_tuning import tuning
from build_reference_draft import ROOT

HERE=Path(__file__).resolve().parent
CASES=('reference','contrast','safe_operation_stop','law_required_stop')
FALLBACKS=('fallback1','fallback2','fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


def build():
    outputs=[]
    for case in CASES:
        base=HERE/('construction.json' if case=='reference' else
                   f'draft-{case}-construction.json')
        original=json.loads(base.read_text())
        primary_entry=json.loads((HERE/f'draft-{case}-compatibility-manifest.json').read_text())['cases'][0]
        entries=[]
        for candidate in FALLBACKS:
            selected=tuning(candidate)
            construction=json.loads(json.dumps(original))
            config=next(item for item in construction['files']
                        if item['path']=='config.json')
            values=json.loads(config['content'])
            values['candidate_id']=candidate
            values['candidate_risk_trigger']=selected.risk_trigger
            config['content']=json.dumps(values,indent=2,sort_keys=True)+'\n'
            construction['candidate_id']=candidate
            construction['risk_trigger']=selected.risk_trigger
            construction['fallback_changed_knobs']=selected.risk_trigger['changed_knobs']
            construction['parent_primary_sha256']=sha(base)
            path=HERE/f'draft-{case}-{candidate}-construction.json'
            write(path,construction)
            entries.append({'id':candidate,'construction':path.name,
                            'construction_sha256':sha(path),
                            'trigger':selected.risk_trigger,
                            'changed_knobs':selected.risk_trigger['changed_knobs']})
            outputs.append({'case':case,'candidate':candidate,
                            'construction_sha256':sha(path)})
        manifest={'format':'worker-execution-manifest',
                  'assignment_id':HERE.name,
                  'runtime_manifest_sha256':sha(ROOT/'runtime/pipeline/SOURCE-MANIFEST.json'),
                  'status':'draft_fallback_offline_only',
                  'cases':[{'case_id':original['case_id'],
                            'construction':base.name,
                            'construction_sha256':sha(base),
                            'fixture_recipe':primary_entry['fixture_recipe'],
                            'measurement_contract':primary_entry['measurement_contract'],
                            'measurement_procedure':primary_entry['measurement_procedure'],
                            'candidate_risk':{'status':'physical',
                                              'reason':'Surveyed spawn, stop overshoot and follower closing are measured risks'},
                            'candidates':entries}]}
        mpath=HERE/f'draft-{case}-fallback-manifest.json'
        write(mpath,manifest)
        for output in outputs[-3:]:
            output['manifest_sha256']=sha(mpath)
    return {'fallbacks':outputs,'count':len(outputs)}


if __name__=='__main__':
    print(json.dumps(build(),sort_keys=True))
