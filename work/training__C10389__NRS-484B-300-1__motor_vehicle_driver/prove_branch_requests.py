"""CPU proof that authored statutory branch requests remain source bound."""
import copy
import hashlib
import json
from pathlib import Path
from branch_requests import CASES, HERE, source, validate


def main():
    source()
    directory=HERE/'cases/branch-requests'
    manifest=json.loads((directory/'manifest.json').read_text())
    if manifest['assignment_id']!=HERE.name or manifest['native_executed'] or manifest['selected_delivery']:
        raise ValueError('Branch request provenance changed')
    reviews={}
    for entry in manifest['entries']:
        suffix=entry['suffix']
        if suffix not in CASES:
            raise ValueError('Unexpected branch case')
        path=directory/entry['path']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:
            raise ValueError('Branch request hash changed')
        rows=[json.loads(line) for line in path.read_text().splitlines()]
        reviews[suffix]=validate(rows,suffix)
    if set(reviews)!=set(CASES):
        raise ValueError('Incomplete statutory branch requests')
    negatives={}
    baseline=[json.loads(line) for line in (directory/'officer_directed_proceed.jsonl').read_text().splitlines()]
    for name,change in [
        ('officer_direction',lambda x:x[100]['officer'].update(requested_direction='none')),
        ('signal_aspect',lambda x:x[100]['device'].update(requested_signal_aspect='green')),
        ('frame_join',lambda x:x[100].update(frame=999)),
        ('source_kind',lambda x:x[100].update(source_kind='original_native')),
        ('missing_frame',lambda x:x.pop()),
    ]:
        rows=copy.deepcopy(baseline);change(rows)
        try:validate(rows,'officer_directed_proceed')
        except ValueError as exc:negatives[name]=str(exc)
        else:raise AssertionError('Altered request accepted: '+name)
    return {'format':'c10389-statutory-branch-request-proof-v1','case_count':len(reviews),
            'comparisons':manifest['comparisons'],'reviews':reviews,'negative_rejections':negatives,
            'native_executed':False,'selected_delivery':False,
            'statutory_outcome_claimed':False}


if __name__=='__main__':
    p=main();target=HERE/'cases/branch-requests/proof.json'
    target.write_text(json.dumps(p,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'case_count':p['case_count'],'negative_rejections':len(p['negative_rejections'])}))
