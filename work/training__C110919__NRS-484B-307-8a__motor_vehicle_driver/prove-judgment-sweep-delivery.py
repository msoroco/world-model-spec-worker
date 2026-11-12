"""Exercise exact sweep source audits and reject synthetic original promotion."""
import hashlib
import json
from pathlib import Path

from judgment_sweep_delivery_audit import audit

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SETS=(('C110919-right-of-way','update041-traffic-timing-sweep-manifest.json',
       'update047-traffic-timing-sweep-matrix-index.json','c110919-update047-timing-matrix'),
      ('C110919-extreme-right','update052-extreme-right-sweep-manifest.json',
       'update052-extreme-right-sweep-matrix-index.json','c110919-update052-lateral-matrix'))

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())

def main():
    outcomes=[];negative={}
    for sweep,manifest_name,index_name,run_name in SETS:
        manifest_path=HERE/manifest_name
        manifest=read(manifest_path);index=read(HERE/index_name)
        if index['manifest_sha256']!=sha(manifest_path):
            raise ValueError('Current sweep source matrix missing')
        for entry in manifest['cases']:
            ident=entry['case_id']
            run=ROOT/'.runtime-work'/run_name/sha(manifest_path)[:12]/ident/'primary'
            attempt=run/'compatibility';processing=run/'saved/v0001/processing.json'
            result=audit(sweep,ident,entry['construction_sha256'],attempt,processing,
                         diagnostic=True)
            if result['passed'] is not False or result['source_shape_passed'] is not True:
                raise ValueError('Diagnostic source accepted or incomplete')
            outcomes.append({'case_id':ident,'sweep_id':sweep,
                'source_sha256':result['source_sha256'],
                'saved_processing_sha256':sha(processing),'original_accepted':False})
            try:audit(sweep,ident,entry['construction_sha256'],attempt,processing,
                      diagnostic=False)
            except ValueError as error:negative[ident+'__synthetic_as_original']=str(error)
            else:raise AssertionError('Synthetic source promoted to original: '+ident)
            try:audit(sweep,ident,'0'*64,attempt,processing,diagnostic=True)
            except ValueError as error:negative[ident+'__wrong_construction']=str(error)
            else:raise AssertionError('Changed construction accepted: '+ident)
    proof={'format':'c110919-judgment-sweep-delivery-source-audit-v1',
           'auditor_sha256':sha(HERE/'judgment_sweep_delivery_audit.py'),
           'cases_checked':len(outcomes),'outcomes':outcomes,
           'negative_rejections':negative,'original_native_accepted':False,
           'canonical_selected':False}
    target=HERE/'update054-judgment-sweep-delivery-audit.json'
    target.write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({'cases_checked':len(outcomes),
        'negative_rejections':len(negative),'proof_sha256':sha(target),
        'original_native_accepted':False}))

if __name__=='__main__':main()
