"""Independent source-bound pedestrian delivery audit with diagnostic mode."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing source: ' + path.name)
    return json.loads(path.read_text())


def audit(case, candidate, attempt, processing, diagnostic):
    manifest = read(HERE / 'execution-manifest.json')
    matches = [entry for entry in manifest['cases'] if entry['case_id'] == case]
    if len(matches) != 1:
        raise ValueError('Exact selected case required')
    entry = matches[0]
    selected = entry if candidate == 'primary' else next(
        (item for item in entry['candidates'] if item['id'] == candidate), None)
    if selected is None:
        raise ValueError('Exact selected candidate required')
    attempt = Path(attempt)
    saved = read(processing)
    result = read(attempt / 'result.json')
    analysis = read(attempt / 'analysis-report.json')
    if diagnostic:
        receipt = read(attempt / 'compatibility.json')
        source_name = 'steady-samples.jsonl' if '__witness_' in case else 'exception-samples.jsonl'
        if any((receipt.get('passed') is not True,
                receipt.get('case_id') != case,
                receipt.get('candidate_id') != candidate,
                receipt.get('construction_sha256') != selected['construction_sha256'],
                receipt.get('negative_removed') != source_name,
                receipt.get('negative_log_sha256') != sha(attempt / 'negative-analysis.log'))):
            raise ValueError('Current diagnostic compatibility receipt differs')
    if any((saved.get('passed') is not True,
            saved.get('recorded_only') is not True,
            saved.get('case_id') != case,
            saved.get('candidate_id') != candidate,
            saved.get('timestamp_joins', {}).get('frames') != 600,
            saved.get('final_video_checks', {}).get('frames') != 600,
            result.get('accepted') is not False,
            result.get('legal_verdict_claimed') is not False)):
        raise ValueError('Current source-bound compatibility or saved receipt differs')
    key = 'steady_entry_and_progress' if '__witness_' in case else 'prior_entry_exception_source_facts'
    measured = analysis['measurements'][key]['value']
    if measured['original_frames'] != 600:
        raise ValueError('Original frame count differs')
    if '__witness_' in case:
        expected = 'before_steady' if case.endswith('witness_1') else 'at_or_after_steady'
        if measured['entry_relative_to_steady'] != expected:
            raise ValueError('First entry versus steady source differs')
    else:
        expected = 'dont_walk_flashing' if case.endswith('exception_1_1') else 'walk'
        if measured['entry_indication'] != expected or not measured['progress_bound']['engineering_surrogate_met']:
            raise ValueError('Prior entry source or progress bound differs')
    if diagnostic:
        if measured['source_kind'] != 'synthetic_scene_request':
            raise ValueError('Diagnostic source provenance differs')
    else:
        if measured['source_kind'] != 'native_observation':
            raise ValueError('Original Native source required')
        context_name = 'steady-context.json' if '__witness_' in case else 'exception-context.json'
        context = read(attempt / context_name)
        pixel = read(attempt / 'signal-observation-audit.json')
        if any((pixel.get('source_kind') != 'independent_original_pixel_review',
                pixel.get('governs_crosswalk') is not True,
                pixel.get('faces_pedestrian') is not True,
                len(pixel.get('frame_observations', [])) != 600,
                context.get('lawful_prior_entry_review') != 'reviewed_original_history',
                result.get('maneuver_completed') is not True)):
            raise ValueError('Independent physical signal, crossing or prior-entry review incomplete')
        cited = context.get('introductory_exceptions')
        if not isinstance(cited, dict) or not {'NRS-484B-287', 'NRS-484B-290', 'NRS-484B-350'} <= set(cited):
            raise ValueError('Cited exception context missing')
        if any(item.get('review_status') != 'reviewed' or not item.get('original_source_refs')
               for item in cited.values()):
            raise ValueError('Cited exception original source review incomplete')
    return {'format': 'c10316-d4-source-bound-delivery-audit',
            'case_id': case, 'candidate_id': candidate,
            'construction_sha256': selected['construction_sha256'],
            'compatibility_sha256': sha(attempt / 'compatibility.json') if diagnostic else None,
            'processing_sha256': sha(Path(processing)),
            'analysis_sha256': sha(attempt / 'analysis-report.json'),
            'source_kind': measured['source_kind'], 'diagnostic_only': diagnostic,
            'physical_or_legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', default='primary')
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--processing', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    result = audit(args.case, args.candidate, args.attempt, args.processing, args.diagnostic)
    if args.output.exists():
        raise ValueError('Audit output already exists')
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'case_id': args.case,
                      'diagnostic_only': args.diagnostic}))


if __name__ == '__main__':
    main()
