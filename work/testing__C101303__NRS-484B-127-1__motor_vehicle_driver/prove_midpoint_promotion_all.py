"""Run exact CPU proofs for every construction under the nine-case manifest."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
MANIFEST=ROOT/'midpoint-promotion-candidate.json'
VALIDATOR=REPO/'.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck'
TEMP=REPO/'.runtime-work/c101303-midpoint-promotion-all-v2'
PROOFS=ROOT/'midpoint-promotion-proofs'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(label, command, stage):
    result=subprocess.run(command,cwd=REPO,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    log=PROOFS/label/(stage+'.log')
    log.parent.mkdir(parents=True,exist_ok=True)
    log.write_text(result.stdout)
    if result.returncode:
        raise ValueError(f'{label} {stage} failed ({result.returncode}); see {log}')
    return {'log':str(log.relative_to(ROOT)),'sha256':sha(log),'exit_code':0}


def main():
    manifest=json.loads(MANIFEST.read_text())
    rows=[(case, candidate, entry)
          for case in manifest['cases']
          for candidate,entry in [('primary',case),*[(x['id'],x) for x in case['candidates']]]]
    if len(rows)!=36 or len(manifest['cases'])!=9:
        raise ValueError('Nine cases with primary and three fallbacks required')
    if not VALIDATOR.is_file():
        raise ValueError('Pinned CPU Lean validator absent')
    py=str(REPO/'.venv-cpu/bin/python')
    runtime=str(REPO/'runtime.py')
    evidence=[]
    for case,candidate,entry in rows:
        case_id=case['case_id']
        label=case_id.rsplit('source_verified_',1)[1]+'-'+candidate
        output=TEMP/label
        construction=ROOT/entry['construction']
        if sha(construction)!=entry['construction_sha256']:
            raise ValueError('Exact construction changed: '+label)
        selected=['--candidate',candidate] if candidate!='primary' else []
        offline=run(label,[py,runtime,'offline','--manifest',str(MANIFEST),
                           '--case',case_id,'--output',str(output/'offline'),*selected],'offline')
        compatibility=run(label,[py,runtime,'compatibility','--manifest',str(MANIFEST),
                           '--case',case_id,*selected,'--output',str(output/'compat'),
                           '--library',str(REPO/'runtime/library'),'--validator',str(VALIDATOR)],'compatibility')
        saved=run(label,[py,runtime,'process-saved','--manifest',str(MANIFEST),
                       '--case',case_id,'--attempt',str(output/'compat'),
                       '--output',str(output/'saved'),'--library',str(REPO/'runtime/library'),
                       '--validator',str(VALIDATOR)],'saved')
        receipt=json.loads((output/'compat/compatibility.json').read_text())
        processing=json.loads((output/'saved/v0001/processing.json').read_text())
        if (receipt.get('passed') is not True or receipt['case_id']!=case_id
                or receipt['candidate_id']!=candidate
                or receipt['construction_sha256']!=entry['construction_sha256']
                or sha(output/'compat/compatibility-analysis.log')!=receipt['log_sha256']
                or sha(output/'compat/negative-analysis.log')!=receipt['negative_log_sha256']):
            raise ValueError('Compatibility or negative receipt differs: '+label)
        if (processing.get('passed') is not True or processing.get('recorded_only') is not True
                or processing.get('originals_preserved') is not True
                or processing.get('candidate_id')!=candidate
                or processing['analysis_revision']['construction_sha256']!=entry['construction_sha256']
                or processing.get('physical_acceptance_claimed') is not False):
            raise ValueError('Saved receipt differs: '+label)
        evidence.append({'case_id':case_id,'candidate_id':candidate,
                         'construction_sha256':entry['construction_sha256'],
                         'offline':offline,'compatibility':compatibility,'saved':saved,
                         'compatibility_receipt_sha256':sha(output/'compat/compatibility.json'),
                         'negative_log_sha256':sha(output/'compat/negative-analysis.log'),
                         'saved_processing_sha256':sha(output/'saved/v0001/processing.json')})
        print(label,'offline compatibility saved passed',flush=True)
    (PROOFS/'proof-index.json').write_text(json.dumps({
        'format':'c101303-nine-case-cpu-proofs',
        'manifest_sha256':sha(MANIFEST),'passed_count':len(evidence),
        'diagnostic_only':True,'physical_acceptance_claimed':False,
        'legal_acceptance_claimed':False,'proofs':evidence},indent=2)+'\n')


if __name__=='__main__':
    main()
