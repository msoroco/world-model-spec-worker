"""Independent exact curb delivery audit; diagnostic mode cannot accept footage."""
import argparse
import hashlib
import json
from pathlib import Path

from physical_audit import audit as physical_audit

HERE=Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path=Path(path)
    if not path.is_file(): raise ValueError('Missing source: '+path.name)
    return json.loads(path.read_text())


def audit(case,candidate,attempt,processing,review,diagnostic):
    manifest=read(HERE/'execution-manifest.json')
    matches=[entry for entry in manifest['cases'] if entry['case_id']==case]
    if len(matches)!=1: raise ValueError('Exact selected case required')
    entry=matches[0]
    selected=entry if candidate=='primary' else next(
        (item for item in entry['candidates'] if item['id']==candidate),None)
    if selected is None: raise ValueError('Exact selected candidate required')
    attempt=Path(attempt)
    compatibility=read(attempt/'compatibility.json') if diagnostic else None
    saved=read(processing)
    result=read(attempt/'result.json')
    analysis=read(attempt/'analysis-report.json')
    if diagnostic and any((compatibility.get('passed') is not True,
                           compatibility.get('case_id')!=case,
                           compatibility.get('candidate_id')!=candidate,
                           compatibility.get('construction_sha256')!=selected['construction_sha256'],
                           compatibility.get('negative_removed')!='curb-samples.jsonl',
                           compatibility.get('negative_log_sha256')!=sha(attempt/'negative-analysis.log'))):
        raise ValueError('Current curb diagnostic compatibility receipt differs')
    if any((saved.get('passed') is not True,
            saved.get('recorded_only') is not True,
            saved.get('case_id')!=case,
            saved.get('candidate_id')!=candidate,
            saved.get('timestamp_joins',{}).get('frames')!=600,
            saved.get('final_video_checks',{}).get('frames')!=600,
            result.get('case_id')!=case,
            result.get('accepted') is not False,
            result.get('legal_verdict_claimed') is not False,
            analysis.get('case_id')!=case)):
        raise ValueError('Current source-bound saved curb receipt differs')
    measured=analysis['measurements']['curb_departure_conditional_margin']['value']
    expected='conditional_yield_possible' if case.endswith('probe_1') else 'conditional_yield_impossible'
    if (measured.get('original_frames')!=600 or
            measured.get('conditional_yield_relation')!=expected or
            measured.get('impossibility_to_yield_proven') is not False or
            measured.get('legal_verdict_claimed') is not False):
        raise ValueError('Original curb source measurement differs')
    if not diagnostic:
        if review is None: raise ValueError('Original Native source required')
        physical=physical_audit(attempt,review)
        if result.get('provenance_kind')!='native_observation' or not result.get('maneuver_completed'):
            raise ValueError('Original Native curb completion required')
    else:
        if measured.get('source_kind')!='synthetic_scene_request':
            raise ValueError('Diagnostic source provenance differs')
        physical=None
    return {'format':'c230222-source-bound-delivery-audit-v1',
            'case_id':case,'candidate_id':candidate,
            'construction_sha256':selected['construction_sha256'],
            'compatibility_sha256':sha(attempt/'compatibility.json') if diagnostic else None,
            'processing_sha256':sha(processing),
            'analysis_sha256':sha(attempt/'analysis-report.json'),
            'physical_review':physical,'diagnostic_only':diagnostic,
            'physical_or_legal_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',required=True)
    parser.add_argument('--candidate',default='primary')
    parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--processing',type=Path,required=True)
    parser.add_argument('--review',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--diagnostic',action='store_true')
    args=parser.parse_args()
    result=audit(args.case,args.candidate,args.attempt,args.processing,args.review,args.diagnostic)
    if args.output.exists(): raise ValueError('Audit output already exists')
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':True,'case_id':args.case,'diagnostic_only':args.diagnostic}))


if __name__=='__main__':
    main()
