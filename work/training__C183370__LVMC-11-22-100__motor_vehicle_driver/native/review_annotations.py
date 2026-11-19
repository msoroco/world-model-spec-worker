"""Bind independent C183370 observations to retained Native camera sources.

This validates a reviewer's source citations. It does not infer a warning from
person proximity, a repair from a survey polygon, or a legal verdict.
"""
import argparse
import hashlib
import json
from pathlib import Path


REQUIRED = ('warning_act', 'newly_repaired_pavement')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _interval(row, first, last):
    interval = row.get('frame_interval')
    if (not isinstance(interval, list) or len(interval) != 2 or
            any(type(x) is not int for x in interval) or
            not first <= interval[0] <= interval[1] <= last):
        raise ValueError('Review frame interval is outside original source')
    return interval


def _citation(row, cameras, first, last):
    camera = row.get('camera')
    if camera not in cameras or row.get('camera_sha256') != cameras[camera]:
        raise ValueError('Review camera source hash differs')
    interval = _interval(row, first, last)
    if not isinstance(row.get('observation'), str) or len(row['observation'].strip()) < 20:
        raise ValueError('Review needs a specific observed fact')
    return interval


def evaluate(analysis, review, *, analysis_sha256):
    if (analysis.get('format') != 'c183370-original-source-analysis-v1' or
            analysis.get('source_kind') != 'original_carla_capture'):
        raise ValueError('Original CARLA source analysis required')
    if review.get('source_analysis_sha256') != analysis_sha256:
        raise ValueError('Review source-analysis hash differs')
    reviewer = review.get('reviewer_id')
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError('Independent reviewer identity required')
    observations = analysis['observations']
    first, last = observations['source_first_frame'], observations['source_last_frame']
    cameras = {row['name']:row['source_sha256'] for row in analysis['camera_sources']}
    if (set(cameras) != set(CAMERAS) or
            any(not isinstance(value,str) or len(value) != 64 or
                any(c not in '0123456789abcdef' for c in value) for value in cameras.values())):
        raise ValueError('Four original cameras required for source review')
    annotations = review.get('annotations')
    if not isinstance(annotations, dict) or not set(REQUIRED) <= annotations.keys():
        raise ValueError('Warning and pavement source annotations required')
    intervals = {}
    for name in REQUIRED:
        row = annotations[name]
        if row.get('observed') is not True:
            raise ValueError(name+' must be affirmatively observed')
        if name == 'warning_act' and row.get('warning_content') != 'against_riding_or_driving_over_identified_pavement':
            raise ValueError('Specific warning content not reviewed')
        if name == 'newly_repaired_pavement' and row.get('condition') not in ('newly_laid','newly_repaired'):
            raise ValueError('Newly laid or repaired condition not reviewed')
        intervals[name] = _citation(row, cameras, first, last)
    overlap = [max(intervals[name][0] for name in REQUIRED),
               min(intervals[name][1] for name in REQUIRED)]
    if overlap[0] > overlap[1]:
        raise ValueError('Warning and pavement observations do not overlap')
    contact = observations['pavement_footprint_contact_frames']
    if any(type(x) is not int or not 0 <= x < observations['source_frames'] for x in contact):
        raise ValueError('Analyzed contact frame index invalid')
    contact_native = [first+x for x in contact]
    concurrent_contact = [x for x in contact_native if overlap[0] <= x <= overlap[1]]
    exception = annotations.get('paving_employee_exception', {'status':'unreviewed'})
    if exception.get('status') not in ('unreviewed','not_actually_engaged','actually_engaged'):
        raise ValueError('Unknown paving employee exception status')
    if exception['status'] != 'unreviewed':
        evidence = exception.get('independent_evidence')
        if (not isinstance(evidence, dict) or
                not isinstance(evidence.get('reference'),str) or
                not isinstance(evidence.get('sha256'),str) or
                len(evidence['sha256']) != 64 or
                not isinstance(evidence.get('observation'),str) or
                len(evidence['observation'].strip()) < 20):
            raise ValueError('Paving employee status needs independent source evidence')
    case = analysis['case']
    if case not in ('reference','contrast'):
        raise ValueError('Unexpected case in original analysis')
    return {
        'format':'c183370-source-review-v1',
        'case':case, 'reviewer_id':reviewer,
        'source_analysis_sha256':analysis_sha256,
        'source_review_sha256':None,
        'warning_and_repair_overlap_frames':overlap,
        'contact_during_reviewed_context_frames':concurrent_contact,
        'requested_contact_context_observed': bool(concurrent_contact) if case == 'reference' else not contact_native,
        'paving_employee_exception_status':exception['status'],
        'evidence_level':'reviewer_attested_source_citations',
        'physical_acceptance_claimed':False,
        'legal_verdict_claimed':False,
    }


def review_attempt(attempt, annotations_path, output):
    attempt, annotations_path, output = map(Path,(attempt,annotations_path,output))
    if output.exists():
        raise ValueError('Preserve prior review receipt; use a new output')
    analysis_path=attempt/'source-analysis.json'
    analysis=json.loads(analysis_path.read_text())
    annotations=json.loads(annotations_path.read_text())
    result=evaluate(analysis,annotations,analysis_sha256=digest(analysis_path))
    result['source_review_sha256']=digest(annotations_path)
    output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--annotations',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    review_attempt(args.attempt,args.annotations,args.output)


if __name__=='__main__':
    main()
