"""Independent exact-source and conditional selection review."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def audit():
    review=json.loads((HERE/'native/selection-review.json').read_text())
    manifest=json.loads((HERE/'execution-manifest.json').read_text())
    source=json.loads((ROOT/'inputs'/HERE.name/'assignment.json').read_text())
    assert review['assignment_id']==manifest['assignment_id']==source['assignment_id']==HERE.name
    assert review['exact_target_clause']==source['law']['text']
    assert review['legal_verdict'] is None and not review['original_native_observed']
    assert len(review['sources'])==4
    for ref in review['sources']:assert sha(ROOT/ref['path'])==ref['sha256']
    assert len(review['unclaimed_branches'])==4 and len(review['physical_unknowns'])>=4
    assert manifest['selection_review']=={'path':'native/selection-review.json',
        'sha256':sha(HERE/'native/selection-review.json')}
    assert len(manifest['cases'])==4 and set(review['selected_case_ids'])=={e['case_id'] for e in manifest['cases']}
    checked=[]
    for entry in manifest['cases']:
        assert entry['kind']=='delivery' and len(entry['candidates'])==3
        configs=[]
        for candidate in [entry]+entry['candidates']:
            path=HERE/candidate['construction']
            assert sha(path)==candidate['construction_sha256']
            construction=json.loads(path.read_text())
            assert construction['case_id']==entry['case_id']
            assert construction['status']=='selected_delivery_preparation_original_unverified'
            config=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
            assert config['status']=='selected_delivery_request_original_unverified'
            assert config['physical_success_claimed'] is False
            assert config['selected_case_id']==entry['case_id']
            assert [c['name'] for c in config['cameras']]==['overview','approach','reference_corner','driver_reference']
            configs.append(config)
            checked.append({'case_id':entry['case_id'],'candidate':config['candidate_id'],
                            'construction_sha256':candidate['construction_sha256']})
        assert len({json.dumps(c['knobs'],sort_keys=True) for c in configs})==4
        for config in configs[1:]:
            assert sum(config['knobs'][k]!=configs[0]['knobs'][k] for k in configs[0]['knobs'])==1
    assert len(checked)==16
    return {'format':'c111256-selected-source-audit','passed':True,'selected_case_count':4,
            'candidate_count':16,'original_observed':False,'scope':'conditional CPU selection only',
            'checked':checked}
if __name__=='__main__':
    result=audit();(HERE/'selected-source-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print('audited source and',result['candidate_count'],'conditional selected constructions')
