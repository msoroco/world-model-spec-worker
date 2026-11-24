"""Finalize an original emergency-vehicle attempt from sealed saved sources."""
import argparse
import json
from pathlib import Path

from measure_emergency import AID, measure


def finalize(source_dir, case_id, output, *, diagnostic=False):
    if case_id not in (AID+'__controlled_1', AID+'__controlled_2'):
        raise ValueError('Exact selected emergency case required')
    source_dir=Path(source_dir)
    ctx=json.loads((source_dir/'emergency_context.json').read_text())
    expected='synthetic_diagnostic' if diagnostic else 'original_source_review'
    if ctx.get('review_kind')!=expected or ctx.get('case_id')!=case_id:
        raise ValueError('Exact case and source review provenance required')
    measured=measure(source_dir)
    measured['case_id']=case_id
    measured['source_review_kind']=expected
    measured['selected_outcome_observed']=None
    measured['physical_acceptance_claimed']=False
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():raise ValueError('Saved report already exists')
    output.write_text(json.dumps(measured,indent=2,sort_keys=True)+'\n')
    return {'case_id':case_id,'samples':measured['samples'],
            'source_review_kind':expected,'physical_acceptance_claimed':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-dir',required=True,type=Path)
    parser.add_argument('--case',required=True)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--diagnostic',action='store_true')
    args=parser.parse_args()
    print(json.dumps(finalize(args.source_dir,args.case,args.output,diagnostic=args.diagnostic),sort_keys=True))
