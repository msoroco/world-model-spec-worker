"""Run source-bound classifier and lifecycle fixtures for nine primaries."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
MANIFEST=ROOT/'midpoint-promotion-candidate.json'
TEMP=REPO/'.runtime-work/c101303-midpoint-promotion-all-v2'
OUT=ROOT/'midpoint-promotion-proofs/physical'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    cases=json.loads(MANIFEST.read_text())['cases']
    if len(cases)!=9:
        raise ValueError('Nine exact primaries required')
    for case in cases:
        label=case['case_id'].rsplit('source_verified_',1)[1]
        folder=OUT/label
        folder.mkdir(parents=True,exist_ok=True)
        saved=TEMP/(label+'-primary')/'saved/v0001/processing.json'
        copied=folder/'primary-saved-processing.json'
        shutil.copyfile(saved,copied)
        processing=json.loads(copied.read_text())
        if (processing.get('passed') is not True or
                processing['analysis_revision']['construction_sha256']!=case['construction_sha256']):
            raise ValueError('Primary saved receipt is not exact: '+label)
        receipt={'format':'worker-physical-preparation-fixtures',
                 'case_id':case['case_id'],
                 'construction_sha256':case['construction_sha256'],
                 'diagnostic_fixture':True,
                 'physical_acceptance_claimed':False,'fixtures':[]}
        for kind in ('complete_motion','incomplete_motion','missing_evidence','lifecycle'):
            target=folder/(kind+'.json')
            command=[str(REPO/'.venv-cpu/bin/python'),str(ROOT/'physical_fixture_proof.py'),
                     '--manifest',str(MANIFEST),'--case',case['case_id'],
                     '--kind',kind,'--output',str(target)]
            if kind=='lifecycle':
                command.extend(['--saved-receipt',str(copied)])
            result=subprocess.run(command,cwd=REPO,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            log=folder/(kind+'.log')
            log.write_text(result.stdout)
            if result.returncode:
                raise ValueError('Physical classifier fixture failed: '+label+'/'+kind)
            if kind=='lifecycle':
                receipt['lifecycle']={'events':json.loads(target.read_text())['events'],
                                      'exit_code':0,'log':str(log.relative_to(ROOT)),
                                      'log_sha256':sha(log),
                                      'fixture_receipt':str(target.relative_to(ROOT))}
            else:
                receipt['fixtures'].append({'kind':kind,'command':' '.join(command),
                                            'exit_code':0,'log':str(log.relative_to(ROOT)),
                                            'log_sha256':sha(log),
                                            'result':str(target.relative_to(ROOT)),
                                            'result_sha256':sha(target)})
        path=folder/'receipt.json'
        path.write_text(json.dumps(receipt,indent=2)+'\n')
        print(label,'three outcomes and lifecycle passed',flush=True)


if __name__=='__main__':
    main()
