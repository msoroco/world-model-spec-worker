"""Retain exact current-runtime statutory CPU receipts; synthetic diagnostics only."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SCRATCH=ROOT/'.runtime-work'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(source.read_text().rstrip()+'\n')
    return sha(target)


def compatibility_path(suffix,candidate):
    if suffix=='numeric_1_0':
        return SCRATCH/'c110454-numeric-current'/suffix/(candidate+'-compat-v2')
    if suffix in ('numeric_1_1','numeric_1_2') and candidate=='primary':
        return SCRATCH/'c110454-numeric-current'/suffix/'primary-compat-v1'
    if suffix in ('exception_1_1','exception_1_2') and candidate=='primary':
        return SCRATCH/'c110454-exception-current'/suffix/'primary-compat-v1'
    return SCRATCH/'c110454-statutory-current-compat'/suffix/(candidate+'-v1')


def main():
    manifest_path=HERE/'current-profile-statutory-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    summary={'format':'c110454-current-statutory-cpu-proof-v3',
             'status':'unselected_diagnostic','manifest_sha256':sha(manifest_path),
             'runtime_manifest_sha256':manifest['runtime_manifest_sha256'],
             'synthetic_fixture':True,'native_executed':False,
             'physical_or_legal_acceptance_claimed':False,'chains':[]}
    for entry in manifest['cases']:
        suffix=entry['case_id'].rsplit('__',1)[-1]
        for candidate in [entry,*entry['candidates']]:
            name=candidate['id']
            compat=compatibility_path(suffix,name)
            offline=SCRATCH/'c110454-statutory-current-offline'/suffix/(name+'-v7')/'offline.log'
            dest=HERE/'current-v3-statutory-proofs'/suffix/name
            files={}
            for filename in ('compatibility.json','compatibility-analysis.log','negative-analysis.log'):
                target=dest/filename
                files[str(target.relative_to(HERE))]=copy(compat/filename,target)
            target=dest/'offline.log'
            files[str(target.relative_to(HERE))]=copy(offline,target)
            receipt=json.loads((dest/'compatibility.json').read_text())
            assert receipt['passed'] is True and len(receipt['checks'])==11
            assert receipt['case_id']==entry['case_id'] and receipt['candidate_id']==name
            assert receipt['construction_sha256']==candidate['construction_sha256']
            assert receipt['fixture_recipe_sha256']==sha(ROOT/entry['fixture_recipe'])
            assert receipt['log_sha256']==sha(dest/'compatibility-analysis.log')
            assert receipt['negative_log_sha256']==sha(dest/'negative-analysis.log')
            summary['chains'].append({'case_id':entry['case_id'],'candidate_id':name,
                                      'construction_sha256':candidate['construction_sha256'],
                                      'recipe_sha256':receipt['fixture_recipe_sha256'],
                                      'checks_passed':len(receipt['checks']),
                                      'negative_removed':receipt['negative_removed'],
                                      'files':files})
    path=HERE/'current-v3-statutory-cpu-proof.json'
    path.write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'chains':len(summary['chains']),'proof_sha256':sha(path)}))

if __name__=='__main__':
    main()
