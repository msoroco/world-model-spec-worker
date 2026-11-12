"""Assemble nine-case selected candidate from exact CPU proof receipts."""
import copy
import hashlib
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
SOURCE=ROOT/'root-config-rebind-candidate.json'
INDEX=ROOT/'midpoint-promotion-proofs/proof-index.json'
OUT=ROOT/'midpoint-promotion-proofs'
TEMP=REPO/'.runtime-work/c101303-midpoint-promotion-all-v3'
OLD='testing__C101303__NRS-484B-127-1__motor_vehicle_driver__source_verified_base'
NEW='testing__C101303__NRS-484B-127-1__motor_vehicle_driver__source_verified_midpoint'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest=json.loads(SOURCE.read_text())
    index=json.loads(INDEX.read_text())
    if index['manifest_sha256']!=sha(SOURCE) or index['passed_count']!=36:
        raise ValueError('Nine-case exact proof index differs')
    proofs={(row['case_id'],row['candidate_id']):row for row in index['proofs']}
    if len(proofs)!=36:
        raise ValueError('Missing exact construction proof')
    midpoint=next(x for x in manifest['cases'] if x['case_id']==NEW)
    if midpoint.get('delivery_acceptance',{}).get('case_id')!=NEW:
        raise ValueError('Midpoint delivery receipt missing before rebinding')
    for case in manifest['cases']:
        label=case['case_id'].rsplit('source_verified_',1)[1]
        physical=OUT/'physical'/label/'receipt.json'
        receipt=json.loads(physical.read_text())
        if receipt['case_id']!=case['case_id'] or receipt['construction_sha256']!=case['construction_sha256']:
            raise ValueError('Physical preparation does not bind primary: '+label)
        case['physical_preparation']={'receipt':str(physical.relative_to(ROOT)),'sha256':sha(physical)}
        for candidate,row in [('primary',case),*[(x['id'],x) for x in case['candidates']]]:
            key=(case['case_id'],candidate)
            proof=proofs[key]
            folder=OUT/(label+'-'+candidate)
            attempt=TEMP/(label+'-'+candidate)
            for source,target in ((attempt/'compat/compatibility.json','compatibility.json'),
                                  (attempt/'compat/compatibility-analysis.log','analysis.log'),
                                  (attempt/'compat/negative-analysis.log','negative.log'),
                                  (attempt/'saved/v0001/processing.json','saved-processing.json')):
                shutil.copyfile(source,folder/target)
            compatibility=json.loads((folder/'compatibility.json').read_text())
            saved=json.loads((folder/'saved-processing.json').read_text())
            if (compatibility['case_id']!=case['case_id']
                    or compatibility['candidate_id']!=candidate
                    or compatibility['construction_sha256']!=row['construction_sha256']
                    or saved['analysis_revision']['construction_sha256']!=row['construction_sha256']):
                raise ValueError('Copied receipt differs: '+str(key))
            offline_command=[str(REPO/'.venv-cpu/bin/python'),str(REPO/'runtime.py'),
                             'offline','--manifest',str(SOURCE),'--case',case['case_id'],
                             '--output',str(attempt/'offline')]
            compat_command=[str(REPO/'.venv-cpu/bin/python'),str(REPO/'runtime.py'),
                            'compatibility','--manifest',str(SOURCE),'--case',case['case_id']]
            if candidate!='primary':
                offline_command.extend(['--candidate',candidate])
                compat_command.extend(['--candidate',candidate])
            compat_command.extend(['--output',str(attempt/'compat'),
                                   '--library',str(REPO/'runtime/library'),
                                   '--validator',str(REPO/'.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck')])
            saved_command=[str(REPO/'.venv-cpu/bin/python'),str(REPO/'runtime.py'),
                           'process-saved','--manifest',str(SOURCE),'--case',case['case_id'],
                           '--attempt',str(attempt/'compat'),'--output',str(attempt/'saved'),
                           '--library',str(REPO/'runtime/library'),
                           '--validator',str(REPO/'.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck')]
            row['offline']={'command':' '.join(offline_command),'exit_code':0,
                            'log':proof['offline']['log'],'log_sha256':proof['offline']['sha256'],
                            'construction_sha256':row['construction_sha256']}
            row['compatibility']={'receipt':str((folder/'compatibility.json').relative_to(ROOT)),
                                  'sha256':sha(folder/'compatibility.json'),
                                  'log':str((folder/'analysis.log').relative_to(ROOT)),
                                  'negative_log':str((folder/'negative.log').relative_to(ROOT)),
                                  'replay_command':' '.join(compat_command),
                                  'replay_log':proof['compatibility']['log'],
                                  'replay_log_sha256':proof['compatibility']['sha256']}
            row['post_capture']={'recorded_only':True,'command':' '.join(saved_command),
                                 'test_log':proof['saved']['log'],
                                 'test_log_sha256':proof['saved']['sha256'],
                                 'test_exit_code':0,
                                 'processing_receipt':str((folder/'saved-processing.json').relative_to(ROOT)),
                                 'processing_sha256':sha(folder/'saved-processing.json')}
            if candidate=='primary':
                row['negative']={'log':row['compatibility']['negative_log']}
                row['post_capture']['feedback_command']='cat '+str(attempt/'saved/v0001/feedback.json')
    target=ROOT/'midpoint-promotion-ready.json'
    target.write_text(json.dumps(manifest,indent=2)+'\n')
    print('nine-case candidate ready for semantic/manifest/comparison review',sha(target))


if __name__=='__main__':
    main()
