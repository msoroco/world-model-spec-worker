"""Independently bind twelve distinct draft fallback offline selections."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
RUN=ROOT/'.runtime-work/c179480-update091-v2/fallbacks-v4'
CASES=('reference','contrast','safe_operation_stop','law_required_stop')
CANDIDATES=('fallback1','fallback2','fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(condition,message):
    if not condition:raise ValueError(message)


def audit():
    records=[]
    for case in CASES:
        primary=HERE/('construction.json' if case=='reference' else
                      f'draft-{case}-construction.json')
        trigger_hashes=set()
        for candidate in CANDIDATES:
            stem=f'{case}-{candidate}'
            path=HERE/f'draft-{stem}-construction.json'
            manifest_path=HERE/f'draft-{case}-fallback-manifest.json'
            construction=read(path)
            manifest=read(manifest_path)
            selection=read(RUN/stem/'candidate-selection.json')
            config=read(RUN/stem/'config.json')
            trigger=construction['risk_trigger']
            require(construction['parent_primary_sha256']==sha(primary) and
                    construction['candidate_id']==candidate and
                    trigger and trigger['source'] and trigger['metric'] and
                    trigger['failure_condition'] and trigger['changed_knobs'],
                    'Fallback trigger or parent differs: '+stem)
            require(config['candidate_id']==candidate and
                    config['candidate_risk_trigger']==trigger and
                    config['case_id']==HERE.name+'__'+case,
                    'Materialized fallback config differs: '+stem)
            candidates=manifest['cases'][0]['candidates']
            selected=next(item for item in candidates if item['id']==candidate)
            require(len(manifest['cases'])==1 and
                    manifest['cases'][0]['construction_sha256']==sha(primary) and
                    selected['construction_sha256']==sha(path) and
                    selected['trigger']==trigger and
                    selection['case_id']==config['case_id'] and
                    selection['candidate_id']==candidate and
                    selection['construction_sha256']==sha(path) and
                    selection['manifest_sha256']==sha(manifest_path),
                    'Offline selection differs: '+stem)
            trigger_hashes.add(json.dumps(trigger,sort_keys=True))
            records.append({'case_id':config['case_id'],
                            'candidate_id':candidate,
                            'construction_sha256':sha(path),
                            'offline_selection_sha256':sha(RUN/stem/'candidate-selection.json')})
        require(len(trigger_hashes)==3,'Fallback risk triggers are not distinct: '+case)
    report={'format':'c179480-fallback-offline-audit-v1','fallbacks':records,
            'count':len(records),'offline_passed':True,
            'compatibility_proven':False,'saved_processing_proven':False,
            'physical_acceptance_claimed':False,
            'canonical_selected':False}
    output=HERE/'update091-v4-fallback-offline-audit.json'
    output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    return {'passed':True,'count':len(records),'audit_sha256':sha(output)}


if __name__=='__main__':
    print(json.dumps(audit(),sort_keys=True))
