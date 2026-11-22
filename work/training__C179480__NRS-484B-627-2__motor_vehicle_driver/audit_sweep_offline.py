"""Independently bind nine draft sweep primaries and 27 offline fallbacks."""
import hashlib
import json
from pathlib import Path

from sweep_case import SWEEPS, resolve

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest=read(HERE/'sweep-candidate-manifest.json')
    offline=read(HERE/'sweep-fallback-offline-index.json')
    primary=read(HERE/'sweep-candidate-primary-offline-index.json')
    canonical=read(HERE/'proposals/canonical-cases.json')
    cases={case['case_id']:case for case in canonical['cases'] if case.get('sweep_id')}
    if (len(cases)!=9 or len(manifest['cases'])!=9 or
            offline['manifest_sha256']!=sha(HERE/'sweep-candidate-manifest.json') or
            primary['manifest_sha256']!=sha(HERE/'sweep-candidate-manifest.json') or
            manifest['runtime_manifest_sha256']!=sha(ROOT/'runtime/pipeline/SOURCE-MANIFEST.json')):
        raise ValueError('Sweep stage or runtime binding changed')
    primary_logs={x['case_id']:x for x in primary['cases']}
    fallback_logs={(x['case_id'],x['candidate_id']):x for x in offline['results']}
    if len(primary_logs)!=9 or len(fallback_logs)!=27:
        raise ValueError('Sweep offline proof matrix is incomplete')
    bound=[]
    for item in manifest['cases']:
        cid=item['case_id'];semantic=cases[cid]
        base,axis,value=resolve(read_config(HERE/item['construction']))
        if (value!=semantic['sweep_point'][axis] or
                item['construction_sha256']!=sha(HERE/item['construction'])):
            raise ValueError('Sweep primary differs from semantic point')
        log=primary_logs[cid]
        if (log['exit_code']!=0 or sha(HERE/log['log'])!=log.get('log_sha256',sha(HERE/log['log'])) or
                read(HERE/log['log']).get('offline_passed') is not True):
            raise ValueError('Primary offline proof missing: '+cid)
        if len(item['candidates'])!=3 or {x['id'] for x in item['candidates']}!=set(
                ('fallback1','fallback2','fallback3')):
            raise ValueError('Three distinct fallback IDs required')
        hashes={item['construction_sha256']}
        for candidate in item['candidates']:
            name=candidate['id'];path=HERE/candidate['construction']
            if candidate['construction_sha256']!=sha(path):
                raise ValueError('Fallback hash changed: '+cid+'/'+name)
            config=read_config(path)
            if config['candidate_id']!=name or resolve(config)!=(base,axis,value):
                raise ValueError('Fallback changes the exact sweep point')
            construction=read(path)
            if (construction.get('parent_primary_sha256')!=item['construction_sha256'] or
                    construction.get('fallback_changed_knobs')!=candidate['changed_knobs'] or
                    construction.get('risk_trigger')!=candidate['trigger']):
                raise ValueError('Fallback trigger/parent binding changed')
            proof=fallback_logs[(cid,name)]
            if (proof['exit_code']!=0 or proof['log_sha256']!=sha(HERE/proof['log']) or
                    read(HERE/proof['log']).get('offline_passed') is not True):
                raise ValueError('Fallback offline proof missing: '+cid+'/'+name)
            hashes.add(candidate['construction_sha256'])
        if len(hashes)!=4:
            raise ValueError('Primary and fallbacks are not distinct')
        bound.append({'case_id':cid,'base_case':base,'sweep_axis':axis,
                      'sweep_value':value,'candidate_count':4})
    return {'format':'c179480-independent-draft-sweep-offline-audit-v1',
            'passed':True,'runtime_manifest_sha256':manifest['runtime_manifest_sha256'],
            'candidate_manifest_sha256':sha(HERE/'sweep-candidate-manifest.json'),
            'canonical_cases_sha256':sha(HERE/'proposals/canonical-cases.json'),
            'cases':bound,'offline_proofs_passed':36,
            'selected_cases':0,'physical_or_legal_acceptance_claimed':False}


def read_config(construction_path):
    construction=read(construction_path)
    return json.loads(next(item['content'] for item in construction['files']
                           if item['path']=='config.json'))


if __name__=='__main__':
    print(json.dumps(audit(),indent=2,sort_keys=True))
