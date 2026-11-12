"""Audit all linked comparisons against 900-frame diagnostic originals."""
import hashlib
import json
import sys
from pathlib import Path

folder=Path(__file__).resolve().parent
repo=folder.parent.parent
sys.path.insert(0,str(folder))
from comparison_audit import audit_pair


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def source(case):
    label=case.rsplit('source_verified_',1)[1]
    if label=='midpoint':
        path=repo/'.runtime-work/c101303-midpoint-comparison-v1/midpoint-projected-history.jsonl'
        receipt=json.loads((folder/'midpoint-promotion-proofs/comparison-proof.json').read_text())
        if (receipt['diagnostic_only'] is not True or
                receipt['source_sha256']['midpoint_projection']!=sha(path)):
            raise ValueError('Midpoint diagnostic projection changed')
        return path
    version='v2' if label=='faster_ego' else 'v1'
    path=repo/'.runtime-work/c101303-full-duration'/(label+'-positive-'+version+'/attempt/vehicle_history.jsonl')
    receipt=json.loads((folder/'delivery-proofs'/label/'diagnostic-audit.json').read_text())
    if (receipt['frames']!=900 or receipt['passed'] is not False or
            receipt['original_sources']['history_sha256']!=sha(path)):
        raise ValueError('Comparison input lacks current full-duration source join: '+case)
    return path


plan=json.loads((folder/'case-plan.json').read_text())
results=[]
for pair in plan['comparisons']:
    left,right=map(source,pair['case_ids'])
    result=audit_pair(folder,pair['comparison_id'],left,right)
    if result['frames']!=900:
        raise ValueError('Comparison did not cover planned duration')
    results.append(result)
    print(json.dumps(result,sort_keys=True))
if len(results)!=9:
    raise ValueError('Expected nine exact controlled comparisons')

pair=next(p for p in plan['comparisons'] if p['comparison_id']=='body_gap')
left,right=map(source,pair['case_ids'])
rows=[json.loads(line) for line in left.read_text().splitlines()]
rows[0]['surface_condition']='synthetic_condition_tamper'
negative=repo/'.runtime-work/c101303-full-duration/comparison-negative-surface-v1.jsonl'
negative.write_text(''.join(json.dumps(row,separators=(',',':'))+'\n' for row in rows))
try:
    audit_pair(folder,'body_gap',negative,right)
except ValueError as error:
    if 'comparison surface differs unexpectedly' not in str(error):
        raise
    print('rejected altered fixed surface:',str(error))
else:
    raise ValueError('Comparison accepted an altered fixed surface')
