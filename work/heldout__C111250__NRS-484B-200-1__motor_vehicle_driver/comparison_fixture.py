"""Exact C111250 comparison audit against independent saved sources."""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize
spec=importlib.util.spec_from_file_location('c111250_delivery_audit',HERE/'delivery_audit.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)

def run(comparison_id,negative=False):
    plan=json.loads((HERE/'case-plan.json').read_text())
    comparison=next((c for c in plan['comparisons'] if c['comparison_id']==comparison_id),None)
    if comparison is None:raise ValueError('unknown exact comparison')
    entries={e['case_id']:e for e in json.loads((HERE/'execution-manifest.json').read_text())['cases']}
    with TemporaryDirectory(prefix='road-half-comparison-',dir=ROOT/'.runtime-work') as temp:
        roots=[]
        for i,case in enumerate(comparison['case_ids']):
            if case not in entries:raise ValueError('comparison member lacks construction')
            target=Path(temp)/str(i)
            materialize(ROOT,ROOT/entries[case]['fixture_recipe'],target)
            roots.append(target)
        if negative:
            contract=roots[1]/'capture_contract.json'
            data=json.loads(contract.read_text());data['duration_s']+=1
            contract.write_text(json.dumps(data)+'\n')
        expected=len((roots[0]/'video_frames.jsonl').read_text().splitlines())
        variable='body_side' if comparison_id.endswith('_body_side') else 'exception_premise'
        result=audit.audit_comparison(*roots,variable,expected_frames=expected)
        return {'comparison_id':comparison_id,'case_ids':comparison['case_ids'],
                'comparison':result,'diagnostic_fixture_only':True,
                'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--comparison',required=True)
    parser.add_argument('--negative',action='store_true');args=parser.parse_args()
    print(json.dumps(run(args.comparison,args.negative),sort_keys=True))
