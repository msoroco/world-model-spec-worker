"""Audit six midpoint fallback pairings on candidate-bound synthetic histories."""
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
sys.path.insert(0,str(ROOT))
from comparison_audit import audit_pair


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest=json.loads((ROOT/'execution-manifest.json').read_text())
    receipt=json.loads((ROOT/'fallback-candidate-source-receipt.json').read_text())
    if (receipt.get('physical_fallback_motion_proven') is not False or
            receipt.get('generator_sha256')!=sha(ROOT/'fallback_candidate_sources.py')
            or len(receipt['sources'])!=27):
        raise ValueError('Selected candidate projections incomplete')
    entries={case['case_id']:case for case in manifest['cases']}
    indexed={(x['case_id'],x['candidate_id']):x for x in receipt['sources']}
    plan=json.loads((ROOT/'case-plan.json').read_text())
    pairs=[x for x in plan['comparisons'] if x['comparison_id'] in
           ('body_gap_midpoint','body_gap_midpoint_closer')]
    if len(pairs)!=2:
        raise ValueError('Both midpoint comparisons required')
    results=[]
    for pair in pairs:
        left_case,right_case=pair['case_ids']
        for candidate in ('fallback1','fallback2','fallback3'):
            left_candidate=candidate
            right_candidate=('primary' if pair['comparison_id']=='body_gap_midpoint_closer'
                             and candidate=='fallback1' else candidate)
            paths=[]
            for case_id,selected_candidate in ((left_case,left_candidate),(right_case,right_candidate)):
                if selected_candidate=='primary':
                    path=REPO/'.runtime-work/c101303-midpoint-comparison-v1/midpoint-projected-history.jsonl'
                    source=json.loads((ROOT/'midpoint-promotion-proofs/comparison-proof.json').read_text())
                    if (not case_id.endswith('__source_verified_midpoint') or
                            sha(path)!=source['source_sha256']['midpoint_projection']):
                        raise ValueError('Midpoint primary source changed')
                    paths.append(path)
                    continue
                spec=indexed[(case_id,selected_candidate)]
                selected=next(c for c in entries[case_id]['candidates'] if c['id']==selected_candidate)
                path=REPO/spec['path']
                if (spec['construction_sha256']!=selected['construction_sha256']
                        or sha(path)!=spec['sha256'] or spec['frames']!=900):
                    raise ValueError('Candidate source differs from selected construction')
                paths.append(path)
            result=audit_pair(ROOT,pair['comparison_id'],*paths,
                              left_candidate=left_candidate,
                              right_candidate=None if right_candidate=='primary' else right_candidate)
            if result['frames']!=900:
                raise ValueError('Midpoint fallback comparison lost frames')
            results.append(result)
            print(pair['comparison_id'],candidate,'passed',flush=True)
    if len(results)!=6:
        raise ValueError('Six midpoint fallback comparisons required')
    target=ROOT/'midpoint-promotion-proofs/fallback-comparison-proof.json'
    target.write_text(json.dumps({
        'format':'c101303-midpoint-fallback-comparison-proof',
        'selected_manifest_sha256':sha(ROOT/'execution-manifest.json'),
        'candidate_source_receipt_sha256':sha(ROOT/'fallback-candidate-source-receipt.json'),
        'diagnostic_only':True,'physical_fallback_motion_proven':False,
        'legal_conclusion':'unresolved','pairings':results},indent=2)+'\n')


if __name__=='__main__':
    main()
