"""Independent exact following source audit; CPU diagnostics never accept footage."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path=Path(path)
    if not path.is_file():raise ValueError('Missing source: '+path.name)
    return json.loads(path.read_text())


def require(value,message):
    if not value:raise ValueError(message)


def audit(case,candidate,attempt,processing,diagnostic):
    manifest=read(HERE/'execution-manifest.json')
    matches=[e for e in manifest['cases'] if e['case_id']==case]
    require(len(matches)==1,'Exact selected case required')
    entry=matches[0]
    selected=entry if candidate=='primary' else next((c for c in entry['candidates'] if c['id']==candidate),None)
    require(selected is not None,'Exact selected candidate required')
    attempt=Path(attempt)
    saved=read(processing)
    result=read(attempt/'result.json')
    analysis=read(attempt/'analysis-report.json')
    value=analysis['measurements']['moving_following_interval']['value']
    require(saved.get('passed') is True and saved.get('recorded_only') is True,'Recorded-only saved processing incomplete')
    require(saved.get('case_id')==case and saved.get('candidate_id')==candidate,'Saved case/candidate differs')
    require(saved.get('analysis_revision',{}).get('construction_sha256')==selected['construction_sha256'],'Saved construction differs')
    require(saved.get('originals_preserved') is True,'Original acquisition was rewritten')
    source_hashes=saved.get('original_source_hashes',{})
    for source in ('analysis-report.json','native_samples.jsonl','video_frames.jsonl','capture/evidence.jsonl','candidate-selection.json'):
        require(source_hashes.get(source)==sha(attempt/source),'Saved proof does not bind original '+source)
    require(saved.get('timestamp_joins',{}).get('frames')==900 and saved['timestamp_joins']['passed'] is True,'Full Native time join incomplete')
    require(saved.get('final_video_checks',{}).get('frames')==900 and saved['final_video_checks']['passed'] is True,'Full video decode incomplete')
    require(result.get('accepted') is False and result.get('legal_verdict_claimed') is False,'Finalizer asserted acceptance or legal verdict')
    require(value.get('following_duration_s')==45.0 and value.get('median_bumper_gap_m')>0,'Source-joined moving following interval incomplete')
    require(value.get('native_highway_status_verified') is False,'Original public-highway authority unexpectedly asserted')
    if diagnostic:
        compatibility=read(attempt/'compatibility.json')
        require(compatibility.get('passed') is True and compatibility.get('case_id')==case,'Diagnostic compatibility differs')
        require(compatibility.get('candidate_id')==candidate and compatibility.get('construction_sha256')==selected['construction_sha256'],'Diagnostic construction differs')
        require(compatibility.get('negative_removed')=='native_samples.jsonl','Diagnostic negative source changed')
        require(compatibility.get('negative_log_sha256')==sha(attempt/'negative-analysis.log'),'Negative source proof changed')
        require(result.get('provenance_kind')=='synthetic_local_diagnostic','Diagnostic provenance differs')
    else:
        context=read(attempt/'following_context.json')
        require(result.get('provenance_kind')=='native_source_shape_unverified' and
                result.get('behavior_attempted') is True and
                context.get('source_kind')=='native_observation','Original Native source required')
        review=read(attempt/'independent-original-review.json')
        require(review.get('source_kind')=='independent_original_capture_review' and review.get('case_id')==case,'Original independent review missing')
        for key in ('all_participants','time_join','full_video_decode','actual_pixels','physical_completion','public_highway_status'):
            require(review.get(key) is True,'Original independent review missing '+key)
        require(review.get('original_source_refs'),'Original source references required')
        for ref in review['original_source_refs']:
            relative=Path(ref.get('path',''))
            require(relative.parts and not relative.is_absolute() and '..' not in relative.parts,'Original review source path invalid')
            require(ref.get('sha256')==sha(attempt/relative),'Original review source hash differs')
    return {'format':'c102304-source-bound-delivery-audit-v1','case_id':case,'candidate_id':candidate,
            'construction_sha256':selected['construction_sha256'],
            'processing_sha256':sha(processing),'analysis_sha256':sha(attempt/'analysis-report.json'),
            'diagnostic_only':diagnostic,'physical_or_legal_acceptance_claimed':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',required=True)
    parser.add_argument('--candidate',default='primary')
    parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--processing',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--diagnostic',action='store_true')
    args=parser.parse_args()
    result=audit(args.case,args.candidate,args.attempt,args.processing,args.diagnostic)
    if args.output.exists():raise ValueError('Audit output already exists')
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':True,'case_id':args.case,'diagnostic_only':args.diagnostic}))
