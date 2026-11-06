"""Independent exact-source, distinct-knob and truthful-status audit."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
SUFFIXES={'below_500_ft':450,'at_500_ft':500,'above_500_ft':550}
CANDIDATES=('primary','fallback1','fallback2','fallback3')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest=json.loads((HERE/'draft-candidate-manifest.json').read_text())
    assert manifest['count']==12 and len(manifest['rows'])==12
    assert manifest['exact_offline_pass_count']==manifest['positive_compatibility_pass_count']==0
    seen=set()
    for row in manifest['rows']:
        suffix=row['case_suffix'];candidate=row['candidate_id']
        assert suffix in SUFFIXES and candidate in CANDIDATES
        assert (suffix,candidate) not in seen
        seen.add((suffix,candidate))
        source=HERE/'draft-sightline'/suffix
        path=HERE/'draft-candidates'/suffix/candidate/'plan.json'
        plan=json.loads(path.read_text())
        assert row['plan_sha256']==sha(path)
        assert plan['case_suffix']==suffix and plan['candidate_id']==candidate
        assert plan['law_id']=='NRS-484B-407' and plan['cell_id']=='C104538'
        assert plan['actor']=='motor_vehicle_driver'
        assert plan['authored_reference_limit_ft']==SUFFIXES[suffix]
        assert plan['source_files']=={name:sha(source/name)
                                      for name in ('road.xodr','obstruction.json','measurement.json')}
        assert plan['selected'] is False and plan['physical_trigger_measured'] is False
        assert row['selected'] is False and row['physical_trigger_measured'] is False
        if candidate!='primary':
            trigger=plan['retry_trigger']
            assert trigger['status']=='unmeasured_physical' and trigger['source'] and trigger['metric'] and trigger['condition']
    assert seen=={(s,c) for s in SUFFIXES for c in CANDIDATES}
    for suffix in SUFFIXES:
        plans=[json.loads((HERE/'draft-candidates'/suffix/c/'plan.json').read_text())
               for c in CANDIDATES]
        original=plans[0]['knobs']
        assert len({p['construction_sha256'] for p in plans})==4
        assert all(sum(p['knobs'][k]!=original[k] for k in original)==1 for p in plans[1:])
        assert len({next(k for k in original if p['knobs'][k]!=original[k])
                    for p in plans[1:]})==3
    return {'passed':True,'case_count':3,'unselected_candidate_plans':12,
            'source_exact':True,'distinct_fallbacks_per_case':3,
            'physical_trigger_measurements':0,'offline_receipts':0,
            'positive_compatibility_receipts':0}


if __name__=='__main__':print(json.dumps(audit(),indent=2))
