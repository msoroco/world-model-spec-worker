"""Independent C109166 source gate; diagnostic mode proves software behavior only."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from native_request import authorize_native_capture
from original_source_audit import audit as audit_original


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing source: ' + path.name)
    return json.loads(path.read_text())


def audit(case, candidate, attempt, processing, diagnostic):
    manifest = read(HERE / 'execution-manifest.json')
    entry = next((row for row in manifest['cases'] if row['case_id'] == case), None)
    if entry is None:
        raise ValueError('Exact selected case required')
    selected = entry if candidate == 'primary' else next(
        (row for row in entry['candidates'] if row['id'] == candidate), None)
    if selected is None:
        raise ValueError('Exact selected candidate required')
    attempt = Path(attempt).resolve()
    saved = read(processing)
    if (saved.get('passed') is not True or saved.get('recorded_only') is not True or
            saved.get('case_id') != case or saved.get('candidate_id') != candidate or
            saved.get('native_revision', {}).get('construction_sha256') != selected['construction_sha256'] or
            saved.get('timestamp_joins', {}).get('frames') != 600 or
            saved.get('final_video_checks', {}).get('frames') != 600):
        raise ValueError('Saved exact case or candidate source receipt differs')
    stage = Path(saved['analysis_directory']).resolve()
    result = read(stage / 'result.json')
    analysis = read(stage / 'analysis-report.json')
    sources = {name: sha(stage / name) for name in
               ('video_frames.jsonl', 'pedestrian-original.jsonl',
                'device-original.jsonl', 'camera-sources.jsonl') if (stage / name).is_file()}
    if len(sources) != 4:
        raise ValueError('Missing source: device-original.jsonl')
    authority = read(stage / 'authority-receipt.json')
    original = audit_original(stage, sources, authority)
    measured = analysis['measurements']['diagonal_first_entry_instruction']['value']
    expected = 'diagonal_walk' if case.endswith('controlled_1') else 'diagonal_dont_walk'
    if (measured['first_entry_instruction'] != expected or
            measured['first_entry_native_frame'] != original['first_entry_native_frame'] or
            result.get('legal_verdict_claimed') is not False):
        raise ValueError('Original first-entry measurement differs')
    exception_source = read(stage / 'exception-applicability-source.json')
    exception_measurement = analysis['measurements']['nrs_484b_290_exception_context']
    if (exception_measurement.get('method') != 'exception_applicability_measurement' or
            exception_measurement.get('sources') != {'exception-applicability-source.json': sha(stage / 'exception-applicability-source.json')} or
            exception_measurement.get('value', {}).get('review_status') != exception_source.get('review_status') or
            exception_measurement.get('value', {}).get('legal_verdict', 'missing') is not None):
        raise ValueError('Source-bound NRS 484B.290 exception measurement differs')
    if diagnostic:
        receipt = read(attempt / 'compatibility.json')
        if (receipt.get('passed') is not True or receipt.get('case_id') != case or
                receipt.get('candidate_id') != candidate or
                receipt.get('construction_sha256') != selected['construction_sha256']):
            raise ValueError('Diagnostic public compatibility identity differs')
    else:
        statute_path = exception_source.get('exact_statute_source_path', '')
        person_path = exception_source.get('person_specific_evidence_path', '')
        if (exception_source.get('review_status') != 'independently_reviewed' or
                exception_source.get('synthetic_diagnostic') is True or
                exception_source.get('original_review_pending') is True or
                not exception_source.get('independent_reviewer') or
                exception_source.get('applicability') not in ('applicable', 'not_applicable', 'undetermined') or
                not statute_path or Path(statute_path).is_absolute() or '..' in Path(statute_path).parts or
                not person_path or Path(person_path).is_absolute() or '..' in Path(person_path).parts or
                exception_source.get('exact_statute_source_sha256') != sha(stage / statute_path) or
                exception_source.get('pedestrian_original_sha256') != sources['pedestrian-original.jsonl'] or
                exception_source.get('person_specific_evidence_sha256') != sha(stage / person_path)):
            raise ValueError('Independent person-specific NRS 484B.290 review incomplete')
        provenance = read(attempt / 'acquisition-provenance.json')
        if provenance.get('provenance_kind') != 'native' or provenance.get('diagnostic_fixture') is True:
            raise ValueError('Original Native acquisition required')
        config = read(attempt / 'config.json')
        authorize_native_capture(stage, authority, config['opendrive_signal_id'])
        pixels = read(stage / 'diagonal-pixel-review.json')
        boundary = read(stage / 'road-boundary-review.json')
        for review, label in ((pixels, 'original device pixels'),
                              (boundary, 'original road boundary')):
            if (review.get('review_status') != 'independently_reviewed' or
                    not review.get('independent_reviewer') or
                    review.get('frame_map_sha256') != sources['video_frames.jsonl'] or
                    review.get('first_entry_native_frame') != measured['first_entry_native_frame']):
                raise ValueError('Independent ' + label + ' review incomplete')
        if (pixels.get('actual_diagonal_instruction') != expected or
                pixels.get('device_id') != 'c109166-diagonal-crossing-head' or
                not pixels.get('source_video_sha256') or
                any(sha(stage / (name + '.mkv')) != pixels['source_video_sha256'].get(name)
                    for name in ('overview', 'approach', 'reference_corner', 'driver_reference'))):
            raise ValueError('Original device pixel evidence differs')
        if (boundary.get('full_body_diagonal_clearance_observed') is not True or
                boundary.get('authorized_diagonal_path_observed') is not True or
                result.get('maneuver_completed') is not True):
            raise ValueError('Original physical diagonal completion unverified')
    return {'format': 'c109166-source-bound-delivery-audit-v1',
            'case_id': case, 'candidate_id': candidate,
            'construction_sha256': selected['construction_sha256'],
            'saved_processing_sha256': sha(processing),
            'analysis_sha256': sha(stage / 'analysis-report.json'),
            'original_source_sha256': sources,
            'exception_source_sha256': sha(stage / 'exception-applicability-source.json'),
            'diagnostic_only': diagnostic,
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
        raise ValueError('Retain previous delivery audit result')
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'case_id': args.case,
                      'diagnostic_only': args.diagnostic}))


if __name__ == '__main__':
    main()
